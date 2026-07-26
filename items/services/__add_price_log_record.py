from decimal import Decimal, ROUND_HALF_UP
from items.models import ItemPriceLog



def add_price_log_record(price, old_price, res):
        if (
            (
                old_price != None
                and
                old_price != Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) 
                and
                res.price1 > 0
            ) or 
            (
                res.price1 > 0
            )
        ):
            ItemPriceLog.objects.create(
                item_id=res.id, 
                price=res.price1, 
                by=res.by
            )
