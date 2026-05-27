from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from .models import *
from .serializers import *


# ─── Вспомогательные permissions ────────────────────────────

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsAdminOrReadOnly(permissions.BasePermission):
    """Админ может всё, остальные — только читать (GET)"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == 'admin'

# ─── Авторизация ─────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/"""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Генерируем токены сразу после регистрации
        refresh = RefreshToken.for_user(user)
        return Response({
            'token':   str(refresh.access_token),
            'refresh': str(refresh),
            'user':    UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    """POST /api/auth/login/"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email    = request.data.get('email', '').strip()
        password = request.data.get('password', '')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'detail': 'Неверный email или пароль'}, status=400)

        if not user.check_password(password):
            return Response({'detail': 'Неверный email или пароль'}, status=400)

        if not user.is_active:
            return Response({'detail': 'Аккаунт заблокирован'}, status=403)

        refresh = RefreshToken.for_user(user)
        return Response({
            'token':   str(refresh.access_token),
            'refresh': str(refresh),
            'user':    UserSerializer(user).data,
        })


class LogoutView(generics.GenericAPIView):
    """POST /api/auth/logout/"""
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
        return Response({'detail': 'Выход выполнен'})


# ─── Профиль ─────────────────────────────────────────────────

class ProfileView(generics.RetrieveUpdateAPIView):
    """GET, PATCH /api/profile/"""
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ModelViewSet):
    """GET /api/users/  — только для admin"""
    queryset           = User.objects.all().order_by('-date_joined')
    serializer_class   = UserSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        from django.db.models import Count
        return qs.annotate(bookings_count=Count('bookings'))

    @action(detail=True, methods=['post'], url_path='topup')
    def topup(self, request, pk=None):
        """POST /api/users/{id}/topup/ — пополнение баланса пользователя администратором"""
        user = self.get_object()
        try:
            amount = Decimal(str(request.data.get('amount', '')))
            if amount <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            return Response({'detail': 'Введи корректную сумму'}, status=400)

        user.balance += amount
        user.save()

        Payment.objects.create(
            user=user, amount=amount,
            type='topup',
            description=f'Пополнение баланса администратором на {amount} ₽',
        )
        return Response({'balance': user.balance, 'message': f'Баланс пополнен на {amount} ₽'})


# ─── Пополнение баланса ───────────────────────────────────────

class TopUpView(generics.GenericAPIView):
    """POST /api/payments/topup/"""
    serializer_class = TopUpSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        user = request.user
        user.balance += amount
        user.save()

        Payment.objects.create(
            user=user, amount=amount,
            type='topup',
            description=f'Пополнение баланса на {amount} ₽',
        )

        return Response({
            'balance': user.balance,
            'message': f'Баланс пополнен на {amount} ₽',
        })


class PaymentHistoryView(generics.ListAPIView):
    """GET /api/payments/history/"""
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


# ─── Компьютеры ───────────────────────────────────────────────

class PCViewSet(viewsets.ModelViewSet):
    """GET /api/pcs/ — чтение для всех, изменение для admin"""
    serializer_class = PCSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'busy_slots']:
            return [permissions.AllowAny()]
        return [IsAdmin()]

    def get_queryset(self):
        qs = PC.objects.select_related('zone').all()
        zone   = self.request.query_params.get('zone')
        s      = self.request.query_params.get('status')
        if zone: qs = qs.filter(zone__zone_type=zone)
        if s:    qs = qs.filter(status=s)
        return qs

    @action(detail=True, methods=['get'], url_path='busy_slots')
    def busy_slots(self, request, pk=None):
        """GET /api/pcs/{id}/busy_slots/?date=YYYY-MM-DD"""
        pc = self.get_object()
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'detail': 'Укажи параметр date (YYYY-MM-DD)'}, status=400)
        try:
            from datetime import date
            target_date = date.fromisoformat(date_str)
        except ValueError:
            return Response({'detail': 'Неверный формат даты'}, status=400)

        bookings = Booking.objects.filter(
            pc=pc,
            status='active',
            start_time__date=target_date,
        )
        slots = [{'start': b.start_time.strftime('%H:%M'), 'end': b.end_time.strftime('%H:%M')}
                 for b in bookings]
        return Response(slots)

# ─── Тарифы ──────────────────────────────────────────────────

class TariffViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/tariffs/"""
    queryset           = Tariff.objects.filter(is_active=True)
    serializer_class   = TariffSerializer
    permission_classes = [permissions.AllowAny]


# ─── Бронирования ─────────────────────────────────────────────

class BookingViewSet(viewsets.ModelViewSet):
    """GET, POST, DELETE /api/bookings/"""
    serializer_class   = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        now = timezone.now()
        Booking.objects.filter(status='active', end_time__lt=now).update(status='completed')
        user = self.request.user
        if user.role == 'admin':
            return Booking.objects.select_related('user', 'pc__zone', 'tariff').all()
        return Booking.objects.filter(user=user).select_related('pc__zone', 'tariff')

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=['get'], url_path='my')
    def my(self, request):
        """GET /api/bookings/my/"""
        now = timezone.now()
        Booking.objects.filter(user=request.user, status='active', end_time__lt=now).update(status='completed')
        qs = Booking.objects.filter(user=request.user).select_related('pc__zone', 'tariff')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """DELETE /api/bookings/{id}/ — отмена"""
        booking = self.get_object()

        if booking.user != request.user and request.user.role != 'admin':
            return Response({'detail': 'Нет доступа'}, status=403)

        if booking.status != 'active':
            return Response({'detail': 'Можно отменить только активное бронирование'}, status=400)

        # Возврат средств (50% если меньше часа до начала)
        now = timezone.now()
        minutes_left = (booking.start_time - now).total_seconds() / 60
        refund = booking.total_price if minutes_left > 60 else booking.total_price * Decimal('0.5')

        booking.status = 'cancelled'
        booking.save()

        booking.pc.status = 'free'
        booking.pc.save()

        booking.user.balance += refund
        booking.user.save()

        Payment.objects.create(
            user=booking.user,
            amount=refund, type='refund',
            description=f'Возврат за отмену бронирования #{booking.pk}',
        )

        return Response({'detail': f'Бронирование отменено. Возврат: {refund} ₽'})


# ─── Турниры ─────────────────────────────────────────────────

class TournamentViewSet(viewsets.ModelViewSet):
    queryset           = Tournament.objects.all()
    serializer_class   = TournamentSerializer
    # Используем новое правило: читать могут все, создавать/редактировать — только админ
    permission_classes =[IsAdminOrReadOnly]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """POST /api/tournaments/{id}/join/"""
        tournament = self.get_object()

        if tournament.status != 'open':
            return Response({'detail': 'Регистрация закрыта'}, status=400)

        if tournament.participants.count() >= tournament.max_participants:
            return Response({'detail': 'Все места заняты'}, status=400)

        _, created = TournamentParticipant.objects.get_or_create(
            tournament=tournament, user=request.user,
        )
        if not created:
            return Response({'detail': 'Ты уже зарегистрирован'}, status=400)

        return Response({'detail': 'Регистрация подтверждена!'})

    @action(detail=False, methods=['get'])
    def my(self, request):
        """GET /api/tournaments/my/"""
        participations = TournamentParticipant.objects.filter(
            user=request.user
        ).select_related('tournament')
        data = []
        for p in participations:
            t = p.tournament
            data.append({
                'id':        t.pk,
                'title':     t.title,
                'game':      t.game,
                'start_time': t.start_time,
                'status':    p.place and 'completed' or 'registered',
                'place':     p.place,
                'prize':     p.prize,
                'team_name': p.team_name,
            })
        return Response(data)


# ─── Новости ─────────────────────────────────────────────────

class NewsViewSet(viewsets.ModelViewSet):
    serializer_class = NewsSerializer
    # Теперь админ редактирует, а пользователи просто читают
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [IsAdmin()]

    def get_queryset(self):
        qs = News.objects.all()
        # Обычные пользователи видят только опубликованные
        if not (self.request.user.is_authenticated and self.request.user.role == 'admin'):
            qs = qs.filter(is_published=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)