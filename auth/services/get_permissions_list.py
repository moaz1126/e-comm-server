from django.contrib.auth.models import Permission
from django.apps import apps



def get_django_permissions(excluded_models=[
	'initialstock',
	'initialcreditbalance', 
	'refillableitemsinitialstockclienthas',
	'refillableitemsinitialstock',
	'itemtransformer',
	'oreitem',
	'requestlog',
	
	'historyentry'
]):
	"""Dynamically generates the permissions dictionary from custom apps,

	excluding built-in Django apps and specified model names.
	"""
	if excluded_models is None:
		excluded_models = []

	# Exclude standard built-in Django apps
	builtin_apps = {
		"auth",
		"contenttypes",
		"sessions",
		"admin",
		"messages",
		"staticfiles",
	}

	# Normalize excluded models to lowercase just in case
	excluded_models = [model.lower() for model in excluded_models]

	permissions = (
		Permission.objects.select_related("content_type")
		.exclude(content_type__app_label__in=builtin_apps)
		.exclude(content_type__model__in=excluded_models)
		.all()
	)

	permissions_dict = {}

	action_mapping = {
		"view": "VIEW",
		"add": "ADD",
		"change": "CHANGE",
		"delete": "DELETE",
	}

	for perm in permissions:
		model_name = perm.content_type.model
		group_key = (
			f"{model_name.upper()}S"
			if not model_name.endswith("s")
			else model_name.upper()
		)

		action_prefix = perm.codename.split("_")[0]
		if action_prefix in action_mapping:
			action_key = action_mapping[action_prefix]

		if group_key not in permissions_dict:
			permissions_dict[group_key] = {}

		permissions_dict[group_key][action_key] = (
			f"{perm.content_type.app_label}.{perm.codename}"
		)

	return permissions_dict



def get_user_permissions(user, excluded_models=[
	'initialstock',
	'initialcreditbalance', 
	'refillableitemsinitialstockclienthas',
	'refillableitemsinitialstock',
	'itemtransformer',
	'oreitem',
	'requestlog',
	
	'historyentry'
]):
    """Generates a dictionary for a given user where each model maps to a

    list of booleans: [can_view, can_add, can_change, can_delete].
    Excludes built-in Django apps and specified model names.
    """
    if excluded_models is None:
        excluded_models = []

    builtin_apps = {
        "auth",
        "contenttypes",
        "sessions",
        "admin",
        "messages",
        "staticfiles",
    }
    excluded_models = [model.lower() for model in excluded_models]

    permissions_dict = {}

    for model in apps.get_models():
        app_label = model._meta.app_label
        if app_label in builtin_apps:
            continue

        model_name = model._meta.model_name
        if model_name in excluded_models:
            continue

        # group_key = (
        #     f"{model_name.upper()}S"
        #     if not model_name.endswith("s")
        #     else model_name.upper()
        # )
        group_key = model_name

        can_view = user.has_perm(f"{app_label}.view_{model_name}")
        can_add = user.has_perm(f"{app_label}.add_{model_name}")
        can_change = user.has_perm(f"{app_label}.change_{model_name}")
        can_delete = user.has_perm(f"{app_label}.delete_{model_name}")

        permissions_dict[group_key] = [can_view, can_add, can_change, can_delete]

    return permissions_dict
