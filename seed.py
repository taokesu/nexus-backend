import os
import django

# Говорим Django где находятся настройки
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Теперь можно импортировать модели
from api.models import Zone, PC, Tariff, User

print('Очищаем старые данные...')
PC.objects.all().delete()
Zone.objects.all().delete()
Tariff.objects.all().delete()

print('Создаём зоны...')
std = Zone.objects.create(name='Стандартная', zone_type='standard', description='RTX 3080, 144 Гц мониторы')
vip = Zone.objects.create(name='VIP-зона',    zone_type='vip',      description='RTX 4090, кресла Herman Miller')
cyb = Zone.objects.create(name='Киберспорт',  zone_type='cyber',    description='240 Гц мониторы, RTX 4080')

print('Создаём компьютеры...')
for i in range(1, 13):
    PC.objects.create(zone=std, number=i, price_per_hour=80,
                      specs='RTX 3080 · i7-12700K · 32GB · 144 Гц')
for i in range(1, 7):
    PC.objects.create(zone=vip, number=i, price_per_hour=180,
                      specs='RTX 4090 · i9-14900K · 64GB · 240 Гц')
for i in range(1, 7):
    PC.objects.create(zone=cyb, number=i, price_per_hour=120,
                      specs='RTX 4080 · i9-13900K · 32GB · 240 Гц')

print('Создаём тарифы...')
Tariff.objects.create(name='Стандарт', price_per_hour=80,  description='Дневное время, стандартная зона')
Tariff.objects.create(name='Ночной',   price_per_hour=50,  description='С 23:00 до 09:00, любая зона')
Tariff.objects.create(name='VIP',      price_per_hour=180, description='VIP-зона, кабинки, Herman Miller')

print('Создаём тестового пользователя...')
if not User.objects.filter(username='testuser').exists():
    user = User.objects.create_user(
        username='testuser',
        email='test@nexus.ru',
        password='password123',
        first_name='Павел',
        last_name='Громов',
        balance=1200,
    )
    print(f'  Пользователь: test@nexus.ru / password123')

print('Создаём администратора...')
if not User.objects.filter(username='admin').exists():
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@nexus.ru',
        password='admin123',
        role='admin',
    )
    print(f'  Администратор: admin@nexus.ru / admin123')

print('✓ Готово! База данных заполнена.')