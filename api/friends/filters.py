
class UserFilter:
    """
    Professional filter class to handle advanced user search and discovery.
    """
    def __init__(self, request):
        self.request = request
        self.params = request.query_params

    def get_user_type(self):
        """Returns the user type to filter by, or None for all."""
        u_type = self.params.get('type')
        if u_type in ['patpal', 'patnabor']:
            return u_type
        return None

    def get_radius(self):
        """Returns the search radius in miles, or None for global search."""
        val = self.params.get('radius')
        if val in ['all', '0', 'none']:
            return None
        try:
            return float(val or 50.0)
        except (ValueError, TypeError):
            return 50.0

    def get_city(self):
        """Returns the city to filter by."""
        return self.params.get('city', '').strip()

    def get_state(self):
        """Returns the state to filter by."""
        return self.params.get('state', '').strip()

    def get_search_query(self):
        """Returns the text search query."""
        return self.params.get('search', '').strip()

    def get_include_friends(self):
        """Returns whether to include existing friends in search results."""
        val = self.params.get('include_friends', 'true').lower()
        return val == 'true'
