from common.services.config_json import get_config_json_data


def customeFilters(obj, queryset, key):
    customeConfig = get_config_json_data().get(key, {})
    
    if obj.request.user.is_superuser: return queryset
    
    if obj.request.user.username in customeConfig['defaultFilters']['users']:
        return queryset.filter(**customeConfig['defaultFilters']['filters'])
    return queryset

def customeViewsUserPermissionHandler(user, ___view_id):
    if not ___view_id: return False

    if user.is_superuser: return True

    customeConfig = get_config_json_data().get('customeViewsUserPermission', {})
    if user.username in customeConfig[___view_id]:
        return True
    return False
