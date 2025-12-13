from rest_framework import generics, permissions, views, response, status
from .serializers import RegisterSerializer, UserProfileUpdateSerializer
from django_otp.plugins.otp_email.models import EmailDevice
from django.contrib.auth import get_user_model
from .tasks import send_verification_email
from google.oauth2 import id_token
from google.auth.transport import requests
from rest_framework_simplejwt.tokens import RefreshToken
import jwt
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
import hashlib
from .models import UserProfile





User = get_user_model()


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


class GoogleSignInView(views.APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        token = request.data.get('id_token')
        
        if not token:
            return response.Response({'error': 'ID token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID 
            )
            
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer')
            
            google_user_id = idinfo['sub']
            email = idinfo['email']
            email_verified = idinfo.get('email_verified', False)
            
            if not email_verified:
                return response.Response({'error': 'Email not verified by Google'}, status=status.HTTP_400_BAD_REQUEST)
            
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email.split('@')[0],
                    'full_name': idinfo.get('name', ''),
                    'is_active': True,  
                }
            )
            
            if created or not hasattr(user, 'google_id'):
                user.google_id = google_user_id
                user.is_google_auth = True
                user.did_google_auth = True
                user.profile_pic = idinfo.get('picture', '')
                user.save()
            
            refresh = RefreshToken.for_user(user)

            print(user.full_name)
            
            return response.Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                # 'user': {
                #     'id': user.id,
                #     'email': user.email,
                #     'name': user.get_full_name(),
                #     'picture': idinfo.get('picture')
                # },
                # 'is_new_user': created
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return response.Response({'error': 'Invalid token', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return response.Response({'error': 'Authentication failed', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class AppleSignInView(views.APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        identity_token = request.data.get('identity_token')
        user_data = request.data.get('user')
        
        if not identity_token:
            return response.Response({'error': 'Identity token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Fetch Apple's public keys
            import requests as http_requests
            from jwt import PyJWKClient
            
            # Get the key ID from token header
            unverified_header = jwt.get_unverified_header(identity_token)
            kid = unverified_header.get('kid')
            
            if not kid:
                return response.Response({'error': 'Invalid token header'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Fetch Apple's public keys and verify signature
            jwks_url = 'https://appleid.apple.com/auth/keys'
            jwks_client = PyJWKClient(jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(identity_token)
            
            # Decode and verify token
            decoded_token = jwt.decode(
                identity_token,
                signing_key.key,
                algorithms=['RS256'],
                audience=settings.APPLE_CLIENT_ID,
                issuer='https://appleid.apple.com'
            )
            
            apple_user_id = decoded_token.get('sub')
            email = decoded_token.get('email')
            email_verified = decoded_token.get('email_verified')
            
            if not apple_user_id:
                return response.Response({'error': 'Invalid Apple token'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Only trust email if it's verified
            if email and not email_verified:
                email = None
            
            if email:
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': email.split('@')[0] if email else f'apple_user_{apple_user_id[:8]}',
                        'full_name': user_data.get('name', {}).get('firstName', '') + ' ' + user_data.get('name', {}).get('lastName', '') if user_data else '',
                        'is_active': True,
                    }
                )
            else:
                user, created = User.objects.get_or_create(
                    apple_id=apple_user_id,
                    defaults={
                        'username': f'apple_user_{apple_user_id[:8]}',
                        'email': f'{apple_user_id}@privaterelay.appleid.com',
                        'full_name': user_data.get('name', {}).get('firstName', '') + ' ' + user_data.get('name', {}).get('lastName', '') if user_data else 'Apple User',
                        'is_active': True,
                    }
                )
            
            if created or not user.apple_id:
                user.apple_id = apple_user_id
                user.is_apple_auth = True
                user.did_apple_auth = True
                user.save()
            
            refresh = RefreshToken.for_user(user)
            
            return response.Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.get_full_name(),
                },
                'is_new_user': created
            }, status=status.HTTP_200_OK)
            
        except jwt.InvalidTokenError as e:
            return response.Response({'error': 'Invalid or expired token', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except jwt.InvalidSignatureError as e:
            return response.Response({'error': 'Token signature verification failed', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return response.Response({'error': 'Authentication failed', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class VerifyOtpView(views.APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        verification_token = request.data.get('token')
        otp = request.data.get('otp')

        if not verification_token or not otp:
            return response.Response({'error': "Email and OTP are required"})
        
        try:
            payload = jwt.decode(verification_token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload['user_id']
        except jwt.PyJWTError:
            return response.Response({'error': 'Invalid or expired token'}, status=400)
        
        try:
            
            user = User.objects.get(pk=user_id)

            if user.is_active:
                return response.Response({'error': 'Account already activated'}, status=status.HTTP_400_BAD_REQUEST)
            
            device = EmailDevice.objects.get(email=user.email)

            if device.verify_token(token=otp):
                user.is_active = True
                user.save()

                refresh = RefreshToken.for_user(user)
                return response.Response({
                    "message": "Email verified successfully", 
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh)
                }, status=status.HTTP_200_OK)
            else :
                return response.Response({"error": "Invalid or expired OTP"}, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return response.Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        




class ResendOtpView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        verification_token = request.data.get("token")
        if not verification_token:
            return response.Response({"error": "Token is required"}, status=400)

        try:
            payload = jwt.decode(
                verification_token,
                options={"verify_exp": False, "verify_signature": False}
            )

            user = User.objects.filter(pk=payload['user_id'], is_active=False).first()

            if not user:
                return response.Response({"error": "No pending registration found"},status=400)

            device, created = EmailDevice.objects.get_or_create(
                user=user,
                defaults={"email": user.email, "name": "Email OTP"}
            )
            device.generate_token()  
            device.save()

            payload = {
                'user_id': str(user.id),
                'exp': timezone.now() + timedelta(minutes=5),
                'iat': timezone.now()
            }
            verification_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

            send_verification_email.delay(device.token, user.email)

            return response.Response({"message": "New OTP sent", "verification_token": verification_token})

        except User.DoesNotExist:
            return response.Response({"error": "User not found"}, status=400)
        




class ForgotPasswordView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return response.Response({"error": "Email is required"}, status=400)

        try:
            user = User.objects.get(email=email, is_active=True)
            device, _ = EmailDevice.objects.get_or_create(
                user=user, defaults={"email": user.email, "name": "Reset"}
            )
            device.generate_token() 

            payload = {
                'user_id': str(user.id),
                'purpose': 'password_reset',
                'exp': timezone.now() + timedelta(minutes=15),
                'iat': timezone.now()
            }
            reset_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

            send_verification_email.delay(device.token, user.email)

            return response.Response({"message": "OTP sent to your email", "reset_token": reset_token})

        except User.DoesNotExist:
            return response.Response({"error": "No active account with this email"}, status=400)
        




class VerifyResetOtpView(views.APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        reset_token = request.data.get("token")
        otp = request.data.get("otp")
        if not reset_token or not otp:
            return response.Response({"error": "Email & OTP required"}, status=400)

        try:
            payload = jwt.decode(reset_token, settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('purpose') != 'password_reset':
                return response.Response({"error": "Invalid token"}, status=400)
            user = User.objects.get(id=payload['user_id'], is_active=True)
        except (jwt.PyJWTError, User.DoesNotExist):
            return response.Response({"error": "Invalid or expired token"}, status=400)
        
        password_fingerprint = hashlib.sha256(user.password.encode()).hexdigest()[:12]
        payload = {
            'user_id': str(user.id),
            'purpose': 'password_reset_new',
            'security_hash': password_fingerprint,
            'exp': timezone.now() + timedelta(minutes=15),
            'iat': timezone.now()
        }
        new_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        try:
            device = EmailDevice.objects.filter(user=user).first()
            if device.verify_token(token=otp):
                return response.Response({
                    "message": "OTP verified",
                    "reset_token": new_token 
                })
            else:
                return response.Response({"error": "Invalid or expired OTP"}, status=400)

        except (User.DoesNotExist, EmailDevice.DoesNotExist):
            return response.Response({"error": "Invalid request"}, status=400)
        

class SetNewPasswordView(views.APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        reset_token = request.data.get("token")           
        new_password = request.data.get("new_password")

        if not reset_token or not new_password:
            return response.Response({"error": "Token and password required"}, status=400)

        try:
            payload = jwt.decode(reset_token, settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('purpose') != 'password_reset_new':
                return response.Response({"error": "Invalid token purpose"}, status=400)
            
            user = User.objects.get(id=payload['user_id'], is_active=True)

            current_fingerprint = hashlib.sha256(user.password.encode()).hexdigest()[:12]
            token_fingerprint = payload.get('security_hash')

            print(token_fingerprint)
            print(current_fingerprint)

            if token_fingerprint != current_fingerprint:
                return response.Response({"error": "This link has already been used. Please request a new one."}, status=400)

            user.set_password(new_password)
            user.save(update_fields=["password"])

            return response.Response({"message": "Password updated successfully"})
        except (User.DoesNotExist, EmailDevice.DoesNotExist):
            return response.Response({"error": "Invalid request"}, status=400)
        



class ChangePasswordView(views.APIView):

    def post(self, request):
        user = request.user
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not current_password or not new_password:
            return response.Response(
                {"error": "Both current_password and new_password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(current_password):
            return response.Response(
                {"error": "Current password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if current_password == new_password:
            return response.Response(
                {"error": "New password must be different from current password"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return response.Response(
            {"message": "Password changed successfully"},
            status=status.HTTP_200_OK
        )
    

class DeleteAccountView(views.APIView):
    def post(self, request):
        user = request.user
        user.delete()
        return response.Response(
            {"message": "Account deleted successfully"},
            status=status.HTTP_200_OK
        )
    


class ProfileUpdateView(views.APIView):
    def patch(self, request):
        profile = request.user.profile if hasattr(request.user, 'profile') else UserProfile.objects.create(user=request.user)
        serializer = UserProfileUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(serializer.data, status=status.HTTP_200_OK)



class DeviceTokenView(views.APIView):
    
    def post(self, request):
        fcm_token = request.data.get('fcm_token')
        
        if not fcm_token:
            return response.Response(
                {'error': 'fcm_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        profile.fcm_token = fcm_token
        profile.fcm_token_updated_at = timezone.now()
        profile.save()
        
        return response.Response({
            'message': 'FCM token registered successfully',
            'updated_at': profile.fcm_token_updated_at
        }, status=status.HTTP_200_OK)
    
    def delete(self, request):
        try:
            profile = request.user.profile
            profile.fcm_token = None
            profile.fcm_token_updated_at = None
            profile.save()
            
            return response.Response({
                'message': 'FCM token removed successfully'
            }, status=status.HTTP_200_OK)
        except UserProfile.DoesNotExist:
            return response.Response(
                {'error': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

