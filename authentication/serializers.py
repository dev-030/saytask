from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .tasks import send_verification_email
from django_otp.plugins.otp_email.models import EmailDevice
from django.utils import timezone
from datetime import timedelta
import jwt
from django.conf import settings
from .models import UserProfile
from subscription.models import SubscriptionPlan, Subscription




User = get_user_model() 





class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "password", "full_name", "gender"]
        extra_kwargs = {
            'email': {'validators': []},
            "password": {"write_only": True}, 
        }

    def validate_email(self, value):
        existing_user = User.objects.filter(email=value).first()
        if existing_user:
            if existing_user.is_active:
                raise serializers.ValidationError("This email is already registered. Please login.")
        return value
    
    def create(self, validated_data):

        email = validated_data.get('email')
        User.objects.filter(email=email, is_active=False).delete()

        validated_data['is_active'] = True # setting user as active on first try
        
        user = User.objects.create_user(**validated_data)


        # ------------------User verification system through code sent via email-------------

        # device = EmailDevice.objects.create(
        #     user=user,
        #     email=user.email,
        #     name="Email",
        #     confirmed=False  
        # )
        # device.generate_token()
        # device.valid_until = timezone.now() + timedelta(minutes=5)
        # device.save()
        # payload = {
        #     'user_id': str(user.id),
        #     'exp': timezone.now() + timedelta(minutes=5), 
        #     'iat': timezone.now(),
        # }
        # verification_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        # send_verification_email.delay(device.token, user.email) 
        # user.verification_token = verification_token

        try:
            free_plan = SubscriptionPlan.objects.get(name='free')
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Free plan is not available. Contact support.")

        Subscription.objects.create(
            user=user,
            plan=free_plan,
            billing_interval='month',
            status='active'
        )

        return user
        
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hasattr(instance, "verification_token"):
            data["verification_token"] = instance.verification_token
        return data








class UserProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.full_name', required=False)
    country = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=15)
    gender = serializers.ChoiceField(choices=User._meta.get_field('gender').choices, required=False, allow_blank=True)
    notifications_enabled = serializers.BooleanField(required=False)

    class Meta:
        model = UserProfile
        fields = [
            'first_name',
            'country',
            'birth_date',
            'phone_number',
            'gender',
            'notifications_enabled',
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        profile_data = validated_data

        if 'full_name' in user_data:
            instance.user.full_name = user_data['full_name']
            instance.user.save()

        for attr, value in profile_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
    
    def to_representation(self, instance):
        return {"message": "Profile updated successfully"}








class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['full_name'] = user.full_name
        return token