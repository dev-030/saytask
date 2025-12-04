from django.urls import path, include
from .views import (RegisterView, VerifyOtpView, ResendOtpView, ForgotPasswordView, 
                    VerifyResetOtpView, SetNewPasswordView, ChangePasswordView, 
                    DeleteAccountView, ProfileUpdateView, DeviceTokenView,
                    GoogleSignInView, AppleSignInView)
from rest_framework_simplejwt.views import ( TokenObtainPairView, TokenRefreshView )
from .serializers import CustomTokenObtainPairSerializer






urlpatterns = [
    path('register/', RegisterView.as_view(), name="user_register"),
    path('token/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair'),
    path('verify-otp/', VerifyOtpView.as_view(), name='verify_otp'),
    path('resend-otp/', ResendOtpView.as_view(), name='resend otp'),
    path("forgot-password/", ForgotPasswordView.as_view()),
    path("verify-reset-otp/", VerifyResetOtpView.as_view()),
    path("set-new-password/", SetNewPasswordView.as_view()),
    path("change-password/", ChangePasswordView.as_view(), name='change_password'),
    path("delete-account/", DeleteAccountView.as_view(), name='delete_account'),
    path('profile/', ProfileUpdateView.as_view(), name='profile-update'),
    path('device-token/', DeviceTokenView.as_view(), name='device-token'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('google-signin/', GoogleSignInView.as_view(), name='google-signin'),
    path('apple-signin/', AppleSignInView.as_view(), name='apple-signin'),
]