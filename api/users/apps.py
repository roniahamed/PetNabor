from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'api.users'

    def ready(self):
        import api.users.signals  # noqa: F401

        # Globally patch Unfold Admin to prevent DataErrors when searching UUIDs
        import uuid
        from unfold.admin import ModelAdmin

        original_get_search_results = ModelAdmin.get_search_results

        def custom_get_search_results(self, request, queryset, search_term):
            import re as _re
            old_search_fields = self.search_fields
            
            if search_term and old_search_fields:
                term = search_term.strip()
                
                # Detect full UUID
                full_uuid = None
                try:
                    full_uuid = uuid.UUID(term)
                except ValueError:
                    pass

                # Detect partial UUID prefix (hex digits and dashes, 7+ chars)
                is_uuid_prefix = bool(
                    full_uuid is None and
                    _re.match(r'^[0-9a-fA-F\-]{7,}$', term)
                )

                if full_uuid:
                    # Exact UUID match — query directly, skip LIKE
                    self.search_fields = [
                        f for f in old_search_fields
                        if not f.endswith('id') and not f.endswith('__id')
                    ]
                    try:
                        base_qs, use_distinct = original_get_search_results(self, request, queryset, search_term)
                    finally:
                        self.search_fields = old_search_fields
                    # Add exact id match
                    id_qs = self.model.objects.filter(id=full_uuid)
                    return (base_qs | id_qs).distinct(), use_distinct

                elif is_uuid_prefix:
                    # Partial UUID — use CAST to text + startswith
                    from django.db.models.functions import Cast
                    from django.db.models import TextField, Q
                    self.search_fields = [
                        f for f in old_search_fields
                        if not f.endswith('id') and not f.endswith('__id')
                    ]
                    try:
                        base_qs, use_distinct = original_get_search_results(self, request, queryset, search_term)
                    finally:
                        self.search_fields = old_search_fields
                    # Cast UUID field to text and do a startswith
                    id_qs = self.model.objects.annotate(
                        id_text=Cast('id', output_field=TextField())
                    ).filter(id_text__startswith=term.lower())
                    return (base_qs | id_qs).distinct(), use_distinct

                else:
                    # Regular text search — strip id fields to avoid DataError
                    self.search_fields = [
                        f for f in old_search_fields
                        if not f.endswith('id') and not f.endswith('__id')
                    ]
                    try:
                        res = original_get_search_results(self, request, queryset, search_term)
                    finally:
                        self.search_fields = old_search_fields
                    return res
            
            return original_get_search_results(self, request, queryset, search_term)
            
        ModelAdmin.get_search_results = custom_get_search_results

        # Globally inject a truncated ID field to prevent table overflow
        from django.utils.html import mark_safe
        
        def short_id(self, obj):
            if hasattr(obj, 'id') and obj.id:
                id_str = str(obj.id)
                prefix = id_str[:8]
                return mark_safe(f'<span title="{id_str}" style="font-family:monospace;">{prefix}</span>')
            return "—"
        short_id.short_description = "ID"
        ModelAdmin.short_id = short_id
