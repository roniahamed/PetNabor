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
