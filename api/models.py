from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Расширенный пользователь"""
    ROLES = [('user', 'Игрок'), ('admin', 'Администратор')]

    phone   = models.CharField(max_length=20, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    role    = models.CharField(max_length=10, choices=ROLES, default='user')
    avatar  = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return self.username


class Zone(models.Model):
    """Игровая зона (Стандарт / VIP / Киберспорт)"""
    ZONE_TYPES = [
        ('standard', 'Стандартная'),
        ('vip',      'VIP'),
        ('cyber',    'Киберспортивная'),
    ]
    name        = models.CharField(max_length=50)
    zone_type   = models.CharField(max_length=20, choices=ZONE_TYPES)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class PC(models.Model):
    """Игровой компьютер"""
    STATUS = [
        ('free',     'Свободен'),
        ('busy',     'Занят'),
        ('reserved', 'Забронирован'),
        ('offline',  'Выключен'),
    ]
    zone             = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='pcs')
    number           = models.PositiveSmallIntegerField()
    specs            = models.TextField(blank=True)
    status           = models.CharField(max_length=10, choices=STATUS, default='free')
    price_per_hour   = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        unique_together = ('zone', 'number')
        ordering = ['zone', 'number']

    @property
    def label(self):
        prefix = {'standard': 'STD', 'vip': 'VIP', 'cyber': 'CYB'}
        return f"{prefix.get(self.zone.zone_type, 'PC')}-{self.number:02d}"

    def __str__(self):
        return self.label


class Tariff(models.Model):
    """Тарифный план"""
    name             = models.CharField(max_length=50)
    description      = models.TextField(blank=True)
    price_per_hour   = models.DecimalField(max_digits=8, decimal_places=2)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    is_active        = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} — {self.price_per_hour} ₽/ч"


class Booking(models.Model):
    """Бронирование"""
    STATUS = [
        ('active',    'Активно'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
    ]
    user        = models.ForeignKey(User,    on_delete=models.CASCADE, related_name='bookings')
    pc          = models.ForeignKey(PC,      on_delete=models.CASCADE, related_name='bookings')
    tariff      = models.ForeignKey(Tariff,  on_delete=models.SET_NULL, null=True, related_name='bookings')
    start_time  = models.DateTimeField()
    end_time    = models.DateTimeField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status      = models.CharField(max_length=10, choices=STATUS, default='active')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.pk} {self.user} → {self.pc}"


class Payment(models.Model):
    """Транзакция по балансу"""
    TYPES = [('topup', 'Пополнение'), ('charge', 'Списание'), ('refund', 'Возврат')]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    booking     = models.OneToOneField(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    amount      = models.DecimalField(max_digits=10, decimal_places=2)   # + пополнение, - списание
    type        = models.CharField(max_length=10, choices=TYPES)
    description = models.CharField(max_length=200, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Tournament(models.Model):
    """Турнир"""
    STATUS = [('open', 'Регистрация'), ('ongoing', 'Идёт'), ('finished', 'Завершён')]

    title            = models.CharField(max_length=100)
    game             = models.CharField(max_length=50)
    description      = models.TextField(blank=True)
    start_time       = models.DateTimeField()
    prize_pool       = models.DecimalField(max_digits=10, decimal_places=2)
    max_participants = models.PositiveSmallIntegerField()
    entry_fee        = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status           = models.CharField(max_length=10, choices=STATUS, default='open')
    participants     = models.ManyToManyField(User, through='TournamentParticipant', blank=True)

    def __str__(self):
        return self.title


class TournamentParticipant(models.Model):
    tournament    = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    user          = models.ForeignKey(User,       on_delete=models.CASCADE)
    team_name     = models.CharField(max_length=50, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    place         = models.PositiveSmallIntegerField(null=True, blank=True)
    prize         = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('tournament', 'user')


class News(models.Model):
    """Новости"""
    CATEGORIES = [
        ('update',     'Обновление'),
        ('tournament', 'Турнир'),
        ('promo',      'Акция'),
        ('event',      'Событие'),
    ]
    author       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    title        = models.CharField(max_length=200)
    content      = models.TextField()
    category     = models.CharField(max_length=20, choices=CATEGORIES)
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title