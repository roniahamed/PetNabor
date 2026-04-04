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
            old_search_fields = self.search_fields
            if search_term and old_search_fields:
                is_uuid = False
                try:
                    uuid.UUID(search_term)
                    is_uuid = True
                except ValueError:
                    pass

                if not is_uuid:
                    # Strip 'id' / '=id' / 'model__id' fields to prevent crash evaluating non-strings
                    self.search_fields = [
                        f for f in old_search_fields 
                        if not f.endswith('id') and not f.endswith('__id')
                    ]
            
            try:
                res = original_get_search_results(self, request, queryset, search_term)
            finally:
                self.search_fields = old_search_fields
            return res
            
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
