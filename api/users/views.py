from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import FirebaseTokenSerializer
from .services import firebase_login_service
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from .serializers import UserSerializer

from .models import  Profile
class FirebaseLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = FirebaseTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        id_token = serializer.validated_data.get('id_token')
        first_name = serializer.validated_data.get('first_name', '')
        last_name = serializer.validated_data.get('last_name', '')
        user_type = serializer.validated_data.get('user_type', 'patnabor')

        try:
            tokens, user = firebase_login_service(id_token, first_name, last_name, user_type)
            
            return Response({
                'message': 'Login successful',
                'access_token': tokens['access'],
                'refresh_token': tokens['refresh'],
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'phone': user.phone,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': user.user_type
                }
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'Something went wrong.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    