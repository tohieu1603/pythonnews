from django.core.management.base import BaseCommand
from django.db import transaction
from apps.stock.models import Symbol
from apps.bots.models import Bot, BotType


class Command(BaseCommand):
    help = 'Tạo 3 bots (Ngắn hạn, Trung hạn, Dài hạn) cho mỗi symbol'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Tạo bots cho một symbol cụ thể (VD: VNM)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Xóa bots cũ và tạo lại',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        symbol_filter = options.get('symbol')
        force = options.get('force', False)

        # Lấy danh sách symbols
        symbols = Symbol.objects.all()
        if symbol_filter:
            symbols = symbols.filter(name=symbol_filter)

        if not symbols.exists():
            self.stdout.write(self.style.ERROR('Không tìm thấy symbol nào!'))
            return

        total_symbols = symbols.count()
        created_count = 0
        skipped_count = 0

        self.stdout.write(f'Bắt đầu tạo bots cho {total_symbols} symbols...\n')

        for symbol in symbols:
            self.stdout.write(f'Processing {symbol.name}...', ending=' ')

            # Nếu force=True, xóa bots cũ
            if force:
                deleted_count = Bot.objects.filter(symbol=symbol).delete()[0]
                if deleted_count > 0:
                    self.stdout.write(self.style.WARNING(f'Đã xóa {deleted_count} bots cũ'), ending=' ')

            # Tạo 3 bots cho mỗi symbol
            for bot_type in BotType:
                bot, created = Bot.objects.get_or_create(
                    symbol=symbol,
                    bot_type=bot_type.value,
                    defaults={
                        'name': f'{symbol.name} - {bot_type.label}'
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {bot_type.label}'),
                        ending=' '
                    )
                else:
                    skipped_count += 1

            self.stdout.write('')  # New line

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Hoàn thành!'))
        self.stdout.write(f'  - Đã tạo: {created_count} bots')
        self.stdout.write(f'  - Đã tồn tại: {skipped_count} bots')
        self.stdout.write(f'  - Tổng symbols: {total_symbols}')
