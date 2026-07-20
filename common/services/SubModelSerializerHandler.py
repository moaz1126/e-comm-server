import json
from django.db import transaction
from rest_framework import serializers



class WritableNestedSubmodelMixin:
	"""
	A generic DRF mixin to handle writable nested submodels (line items) 
	supporting actions: 'existing', 'create', 'update', 'delete', and 
	handling both raw lists and JSON string payloads (e.g. from FormData).

	Class Attributes to Configure:
	- SUBMODEL: The target Django model for the submodel lines.
	- SUBMODEL_FK: The parent foreign key name on the submodel (e.g., 'maintenance').
	- SUBMODEL_FIELD: The name of the field in the payload/serializer (e.g., 'parts').
	"""
	SUBMODEL = None
	SUBMODEL_FK = None
	SUBMODEL_FIELD = 'parts'

	def to_internal_value(self, data):
		mutable = data.copy() if hasattr(data, 'copy') else dict(data)
		field_name = self.SUBMODEL_FIELD
		json_field_name = f"{field_name}_json"

		raw_rows = None
		if field_name in mutable and isinstance(mutable[field_name], (list, tuple)):
			raw_rows = mutable.pop(field_name)
		elif json_field_name in mutable:
			pj = mutable.get(json_field_name, '')
			if pj:
				try:
					raw_rows = json.loads(pj)
				except json.JSONDecodeError as exc:
					raise serializers.ValidationError({json_field_name: f'Invalid JSON: {exc}'})
			mutable.pop(json_field_name, None)

		validated = super().to_internal_value(mutable)
		validated['_raw_submodel_rows'] = raw_rows or []
		return validated

	def validate(self, attrs):
		attrs = super().validate(attrs)
		raw_rows = attrs.pop('_raw_submodel_rows', [])
		field_name = self.SUBMODEL_FIELD
		
		row_errors = []
		clean_rows = []
		has_errors = False

		for row in raw_rows:
			action = row.get('_action', 'existing')
			err = {}

			if action == 'existing':
				clean_rows.append({'_action': 'existing', '_row': row})
				row_errors.append({})
				continue

			if action in ('create', 'update'):
				try:
					row = self.validate_submodel_row(row, action)
				except serializers.ValidationError as e:
					err.update(e.detail if isinstance(e.detail, dict) else {'non_field_errors': e.detail})

			elif action == 'delete':
				row_id = row.get('id')
				if not row_id:
					clean_rows.append({'_action': 'skip'})
					row_errors.append({})
					continue
				clean_rows.append({'_action': 'delete', 'id': row_id})
				row_errors.append({})
				continue

			if err:
				has_errors = True
			clean_rows.append({**row, '_action': action})
			row_errors.append(err)

		if has_errors:
			raise serializers.ValidationError({field_name: row_errors})

		attrs['_clean_submodel_rows'] = clean_rows
		return attrs

	def validate_submodel_row(self, row, action):
		"""Hook to inject custom row validation and data coercion per submodel."""
		return row

	@transaction.atomic
	def create(self, validated_data):
		rows = validated_data.pop('_clean_submodel_rows', [])
		instance = super().create(validated_data)
		self._apply_submodel_rows(instance, rows)
		return instance

	@transaction.atomic
	def update(self, instance, validated_data):
		rows = validated_data.pop('_clean_submodel_rows', [])
		instance = super().update(instance, validated_data)
		self._apply_submodel_rows(instance, rows)
		return instance

	def _apply_submodel_rows(self, instance, rows):
		submodel_cls = self.SUBMODEL
		fk_name = self.SUBMODEL_FK
		if not submodel_cls or not fk_name:
			return

		for row in rows:
			action = row.get('_action')

			if action in ('existing', 'skip'):
				continue

			elif action == 'create':
				kwargs = self.get_submodel_create_kwargs(instance, row)
				kwargs[fk_name] = instance
				submodel_cls.objects.create(**kwargs)

			elif action == 'update':
				row_id = row.get('id')
				if not row_id:
					kwargs = self.get_submodel_create_kwargs(instance, row)
					kwargs[fk_name] = instance
					submodel_cls.objects.create(**kwargs)
					continue
				try:
					sub_obj = submodel_cls.objects.get(pk=row_id, **{fk_name: instance})
				except submodel_cls.DoesNotExist:
					raise serializers.ValidationError(
						{self.SUBMODEL_FIELD: f'Record with id {row_id} does not belong to this parent instance.'}
					)
				
				update_kwargs = self.get_submodel_update_kwargs(instance, row, sub_obj)
				for key, val in update_kwargs.items():
					setattr(sub_obj, key, val)
				sub_obj.save()

			elif action == 'delete':
				row_id = row.get('id')
				submodel_cls.objects.filter(pk=row_id, **{fk_name: instance}).delete()

	def get_submodel_create_kwargs(self, instance, row):
		"""Hook to build kwargs for creating a submodel instance."""
		return row

	def get_submodel_update_kwargs(self, instance, row, sub_obj):
		"""Hook to build kwargs for updating a submodel instance."""
		return row
