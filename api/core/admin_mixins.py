import uuid
from django.db.models import Q

class UUIDSearchMixin:
    """
    Mixin to gracefully handle UUID searches without crashing standard text search fields.
    When a valid UUID is pasted into the admin search bar, it supplements the search results
    with exact ID matches. Otherwise, it simply falls back to the configured search_fields.
    """
    def get_search_results(self, request, queryset, search_term):
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
                    base_qs, use_distinct = super().get_search_results(request, queryset, search_term)
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
                    base_qs, use_distinct = super().get_search_results(request, queryset, search_term)
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
                    res = super().get_search_results(request, queryset, search_term)
                finally:
                    self.search_fields = old_search_fields
                return res
        
        return super().get_search_results(request, queryset, search_term)

    def short_id(self, obj):
        """Globally injected truncated ID field to prevent table overflow"""
        from django.utils.html import mark_safe
        if hasattr(obj, 'id') and obj.id:
            id_str = str(obj.id)
            prefix = id_str[:8]
            return mark_safe(f'<span title="{id_str}" style="font-family:monospace;">{prefix}</span>')
        return "—"
    short_id.short_description = "ID"

    def get_fieldsets(self, request, obj=None):
        if self.fieldsets:
            return super().get_fieldsets(request, obj)
        
        # Dynamically build fieldsets into grouped structures for robust layout
        fields = super().get_fields(request, obj)
        
        timestamps = [f for f in fields if f in ('created_at', 'updated_at', 'date_joined')]
        relations = [f for f in fields if f in ('user', 'author', 'sender', 'receiver', 'blocker', 'blocked_user', 'story', 'post', 'blog', 'wallet', 'related_user')]
        stats = [f for f in fields if f in ('likes_count', 'comments_count', 'shares_count', 'display_deleted')]
        
        # Primary attributes excluding separated sets
        main_fields = [f for f in fields if f not in timestamps and f not in relations and f not in stats and f != 'id']
        
        computed_fieldsets = []
        
        # Primary identifiers and editable settings
        if 'id' in fields:
            main_fields.insert(0, 'id')
            
        if main_fields:
            computed_fieldsets.append((None, {
                "fields": main_fields,
            }))
            
        if relations:
            computed_fieldsets.append(("Relations & Associations", {
                "fields": relations,
                "classes": ["tab"],
            }))
            
        if stats:
             computed_fieldsets.append(("Metrics", {
                 "fields": stats,
                 "classes": ["collapse"],
             }))
            
        if timestamps:
            computed_fieldsets.append(("Timestamps & Tracking", {
                "fields": timestamps,
                "classes": ["collapse"],
            }))
            
        return computed_fieldsets
