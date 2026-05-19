from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Zone, PC, Tariff, Booking, Payment, Tournament, TournamentParticipant, News
from decimal import Decimal

class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'password', 'password2')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Пароли не совпадают'})
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'Этот email уже занят'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'phone', 'balance', 'role', 'avatar', 'date_joined')
        read_only_fields = ('id', 'balance', 'role', 'date_joined')


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Zone
        fields = '__all__'


class PCSerializer(serializers.ModelSerializer):
    zone_type = serializers.CharField(source='zone.zone_type', read_only=True)
    zone_name = serializers.CharField(source='zone.name',      read_only=True)
    label     = serializers.ReadOnlyField()

    class Meta:
        model  = PC
        fields = ('id', 'zone', 'zone_type', 'zone_name', 'number', 'label', 'specs', 'status', 'price_per_hour')


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Tariff
        fields = '__all__'


class BookingSerializer(serializers.ModelSerializer):
    pc_label      = serializers.CharField(source='pc.label',        read_only=True)
    tariff_name   = serializers.CharField(source='tariff.name',     read_only=True)
    user_username = serializers.CharField(source='user.username',   read_only=True)
    user_full_name = serializers.SerializerMethodField()

    class Meta:
        model  = Booking
        fields = ('id', 'user', 'user_username', 'user_full_name', 'pc', 'pc_label',
                  'tariff', 'tariff_name', 'start_time', 'end_time',
                  'total_price', 'status', 'created_at')
        read_only_fields = ('user', 'total_price', 'status', 'created_at')

    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    def validate(self, data):
        # Проверка пересечения времён для этого ПК
        pc         = data['pc']
        start_time = data['start_time']
        end_time   = data['end_time']

        if end_time <= start_time:
            raise serializers.ValidationError('Время окончания должно быть позже начала')

        overlap = Booking.objects.filter(
            pc=pc,
            status='active',
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if self.instance:
            overlap = overlap.exclude(pk=self.instance.pk)
        if overlap.exists():
            raise serializers.ValidationError({'pc': 'Это место уже занято в выбранное время'})

        return data

    def create(self, validated_data):
        user   = self.context['request'].user
        pc     = validated_data['pc']
        tariff = validated_data['tariff']

        # Расчёт стоимости
        hours = Decimal((validated_data['end_time'] - validated_data['start_time']).seconds) / Decimal(3600)
        price = round(tariff.price_per_hour * hours, 2)

        if user.balance < price:
            raise serializers.ValidationError('Недостаточно средств на балансе')

        booking = Booking.objects.create(user=user, total_price=price, **validated_data)

        # Списание с баланса
        user.balance -= price
        user.save()

        # Запись транзакции
        Payment.objects.create(
            user=user, booking=booking,
            amount=-price, type='charge',
            description=f'Бронирование {pc.label}',
        )

        # Обновить статус ПК
        pc.status = 'reserved'
        pc.save()

        return booking


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Payment
        fields = ('id', 'amount', 'type', 'description', 'created_at')


class TopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=50)

    def validate_amount(self, value):
        if value < 50:
            raise serializers.ValidationError('Минимальная сумма пополнения — 50 ₽')
        return value


class TournamentSerializer(serializers.ModelSerializer):
    participants_count = serializers.SerializerMethodField()
    is_joined          = serializers.SerializerMethodField()

    class Meta:
        model  = Tournament
        fields = ('id', 'title', 'game', 'description', 'start_time',
                  'prize_pool', 'max_participants', 'participants_count',
                  'entry_fee', 'status', 'is_joined')

    def get_participants_count(self, obj):
        return obj.participants.count()

    def get_is_joined(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.participants.filter(pk=request.user.pk).exists()
        return False


class NewsSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model  = News
        fields = ('id', 'author', 'author_name', 'title', 'content', 'category', 'is_published', 'created_at')
        read_only_fields = ('author', 'created_at')

    def get_author_name(self, obj):
        if obj.author:
            return f"{obj.author.first_name} {obj.author.last_name}".strip() or obj.author.username
        return 'Команда NEXUS'