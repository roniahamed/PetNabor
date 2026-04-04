import uuid
from django.db.models import Q

class UUIDSearchMixin:
    """
    Mixin to gracefully handle UUID searches without crashing standard text search fields.
    When a valid UUID is pasted into the admin search bar, it supplements the search results
    with exact ID matches. Otherwise, it simply falls back to the configured search_fields.
    """
    def get_search_results(self, request, queryset, search_term):
        # Base string searches via search_fields
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if search_term:
            try:
                # If the user typed a valid UUID, also filter by id
                parsed_uuid = uuid.UUID(search_term)
                # Ensure the original filtering + the UUID filtering are combined
                queryset = queryset | self.model.objects.filter(id=parsed_uuid)
            except ValueError:
                pass
                
        return queryset, use_distinct

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
