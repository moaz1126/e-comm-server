import json

from django.db import transaction
from rest_framework import serializers

from common.encoder import MixedRadixEncoder
from common.services.NumberValidator import NumberValidator
from common.utility.audit_info_dateformatter import audit_info_dateformatter

from .models import Maintenance, TransactionSpareParts
from items.models import Items    # adjust import to your actual Items location


class SparePartLineSerializer(serializers.ModelSerializer):
    """
    Serializer for a single TransactionSpareParts row.

    Incoming shape (from the client's parts array):
        {
            "id":         <int|null>,   # null for new rows
            "spare_part": <int>,        # FK to Items
            "quantity":   "1.50",
            "_action":    "create" | "update" | "delete" | "existing"
        }

    _action is not a model field — we pop it in the parent serializer
    before calling save/delete.
    """

    # Write with a PK, read back with the object so the client gets the name.
    # spare_part_id = serializers.PrimaryKeyRelatedField(
    #     queryset=Items.objects.all(),
    #     source='spare_part',
    #     write_only=False,
    # )
    _spare_part_name = serializers.ReadOnlyField(source='spare_part.name')
    _audit_info = serializers.SerializerMethodField()


    class Meta:
        model = TransactionSpareParts
        fields = ['id', '_spare_part_name', 'spare_part', 'quantity', '_audit_info']
        read_only_fields = ['id', '_spare_part_name', '_audit_info']

    def get__audit_info(self, obj):
        return audit_info_dateformatter(obj)

    # def get__spare_part(self, obj):
    #     return {'id': obj.spare_part_id, 'name': obj.spare_part.name}


class MaintenanceSerializer(serializers.ModelSerializer):
    """
    Full Maintenance serializer with writable nested spare parts.

    The `parts` key is NOT a regular nested serializer field — it arrives as
    a JSON string in `parts_json` (from the Next.js FormData) OR as a plain
    list when the client sends application/json.  We normalise both in
    to_internal_value() and store the parsed list on the instance so
    create() / update() can handle it.

    The `_action` field on each part row is consumed here and never reaches
    the SparePartLineSerializer.
    """


    _client_name = serializers.ReadOnlyField(source='client.name')
    _item_name = serializers.ReadOnlyField(source='item.name')
    _maintained_by_name = serializers.SerializerMethodField()
    # parts = TransactionSparePartsSerializer(many=True, read_only=False, required=False)
    _hashed_id = serializers.SerializerMethodField()
    _audit_info = serializers.SerializerMethodField()



    # Read-only nested representation returned in GET responses
    parts = SparePartLineSerializer(many=True, required=False)

    # Accept `parts_json` as a write-only JSON string (FormData path)
    parts_json = serializers.CharField(write_only=True, required=False, allow_blank=True)

    # client  = serializers.PrimaryKeyRelatedField(queryset=Party.objects.all())
    # item    = serializers.PrimaryKeyRelatedField(queryset=Items.objects.all())
    # by      = serializers.PrimaryKeyRelatedField(
    #     queryset=Employee.objects.all(), allow_null=True, required=False
    # )

    class Meta:
        model = Maintenance
        fields = [
            # 'id',
            'client',
            'serial_number',
            'item',
            'status',           # read-only in practice (set by model.save())
            'date_in',
            'maintenance_date',
            'date_out',
            'maintained_by',
            'malfunctions',
            'notes',
            'parts',            # read
            'parts_json',       # write (FormData path)
            '_client_name', '_item_name', '_maintained_by_name', '_hashed_id', '_audit_info'
        ]
        read_only_fields = ['id', 'status', '_maintained_by_name']
        extra_kwargs = {
            # 'date_in': {'required': False},
            # 'malfunctions': {'allow_null': True},
            # 'notes': {'allow_null': True},
            # 'age': {'required': False, 'allow_null': True}
        }
    
    def get__hashed_id(self, obj):
        return MixedRadixEncoder().encode(obj.id)
    
    def get__audit_info(self, obj):
        return audit_info_dateformatter(obj)
    
    def get__maintained_by_name(self, obj):
        return f"{obj.maintained_by.first_name} {obj.maintained_by.last_name}" if obj.maintained_by else " - "

    # ── normalise incoming parts ──────────────────────────────────────────────

    def to_internal_value(self, data):
        # Support both FormData (parts_json string) and JSON (parts list).
        # We handle parts separately so we can pop parts_json cleanly.
        mutable = data.copy() if hasattr(data, 'copy') else dict(data)

        if not mutable.get('date_in'):  
            mutable.pop('date_in', None)

        raw_parts = None
        if 'parts' in mutable and isinstance(mutable['parts'], (list, tuple)):
            raw_parts = mutable.pop('parts')
        elif 'parts_json' in mutable:
            pj = mutable.get('parts_json', '')
            if pj:
                try:
                    raw_parts = json.loads(pj)
                except json.JSONDecodeError as exc:
                    raise serializers.ValidationError({'parts_json': f'Invalid JSON: {exc}'})
            mutable.pop('parts_json', None)

        validated = super().to_internal_value(mutable)
        validated['_raw_parts'] = raw_parts or []
        return validated

    # ── validate parts list ───────────────────────────────────────────────────

    def validate(self, attrs):
        attrs = super().validate(attrs)
        raw_parts  = attrs.pop('_raw_parts', [])
        part_errors = []
        clean_parts = []
        has_errors  = False

        for i, row in enumerate(raw_parts):
            action = row.get('_action', 'existing')
            err    = {}

            if action == 'existing':
                # Nothing to write — skip validation entirely
                clean_parts.append({'_action': 'existing', '_row': row})
                part_errors.append({})
                continue

            if action in ('create', 'update'):
                sp_id = row.get('spare_part')
                if not sp_id:
                    err['spare_part'] = 'This field is required.'
                else:
                    try:
                        spare_part = Items.objects.get(pk=sp_id)
                    except Items.DoesNotExist:
                        err['spare_part'] = f'Item with id {sp_id} does not exist.'
                    else:
                        row['_spare_part_obj'] = spare_part

                v, error = NumberValidator._coerce_to_numeric(row.get('quantity', 1))
                if error:
                    err['quantity'] = error    
                elif v <= 0 or v >= 9999999.99:
                    err['quantity'] = 'unsupported value'
                else:
                    row['_qty_decimal'] = v

            elif action == 'delete':
                part_id = row.get('id')
                if not part_id:
                    # Brand-new row deleted before save — nothing to do
                    clean_parts.append({'_action': 'skip'})
                    part_errors.append({})
                    continue
                clean_parts.append({'_action': 'delete', 'id': part_id})
                part_errors.append({})
                continue

            if err:
                has_errors = True
            clean_parts.append({**row, '_action': action})
            part_errors.append(err)

        if has_errors:
            raise serializers.ValidationError({'parts': part_errors})

        attrs['_clean_parts'] = clean_parts
        return attrs

    # ── create ────────────────────────────────────────────────────────────────

    @transaction.atomic
    def create(self, validated_data):
        parts = validated_data.pop('_clean_parts', [])
        instance = Maintenance.objects.create(**validated_data)
        self._apply_parts(instance, parts)
        return instance

    # ── update ────────────────────────────────────────────────────────────────

    @transaction.atomic
    def update(self, instance, validated_data):
        parts = validated_data.pop('_clean_parts', [])

        # Update scalar fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        self._apply_parts(instance, parts)
        return instance

    # ── shared parts dispatch ─────────────────────────────────────────────────

    def _apply_parts(self, maintenance, parts):
        """
        Dispatch each row according to its _action.
        Runs inside the caller's atomic block — any exception rolls back everything.
        """
        for row in parts:
            action = row.get('_action')

            if action in ('existing', 'skip'):
                continue

            elif action == 'create':
                TransactionSpareParts.objects.create(
                    maintenance=maintenance,
                    spare_part=row['_spare_part_obj'],
                    quantity=row['_qty_decimal'],
                    created_by=maintenance.created_by,
                    last_updated_by=maintenance.last_updated_by
                )

            elif action == 'update':
                part_id = row.get('id')
                if not part_id:
                    # Defensive: treat as create if id somehow missing
                    TransactionSpareParts.objects.create(
                        maintenance=maintenance,
                        spare_part=row['_spare_part_obj'],
                        quantity=row['_qty_decimal'],
                        # created_by=maintenance.created_by,
                        last_updated_by=maintenance.last_updated_by
                    )
                    continue
                try:
                    part = TransactionSpareParts.objects.get(
                        pk=part_id, maintenance=maintenance
                    )
                except TransactionSpareParts.DoesNotExist:
                    raise serializers.ValidationError(
                        {'parts': f'Part with id {part_id} does not belong to this maintenance record.'}
                    )
                part.spare_part         = row['_spare_part_obj']
                part.quantity           = row['_qty_decimal']
                part.last_updated_by    = maintenance.last_updated_by
                part.last_updated_at    = maintenance.last_updated_at
                part.save()

            elif action == 'delete':
                part_id = row.get('id')
                TransactionSpareParts.objects.filter(
                    pk=part_id, maintenance=maintenance
                ).delete()












class TransactionSparePartsSerializer(serializers.ModelSerializer):
    _spare_part_name = serializers.ReadOnlyField(source='spare_part.name')

    class Meta:
        model = TransactionSpareParts
        fields = ['id', 'spare_part', 'spare_part_name', 'quantity', 'created_at', 'last_updated_at']

