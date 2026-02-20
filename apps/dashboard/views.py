from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Sum, Count, Q


@login_required
def dashboard(request):
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_7 = today - timedelta(days=7)

    date_filter = request.GET.get('range', '7days')
    if date_filter == 'yesterday':
        start_date = yesterday
        end_date = yesterday
    elif date_filter == 'custom':
        from datetime import datetime
        start_date = request.GET.get('start', str(last_7))
        end_date = request.GET.get('end', str(today))
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except Exception:
            start_date = last_7
            end_date = today
    else:
        start_date = last_7
        end_date = today

    try:
        from apps.rfq.models import RFQ
        from apps.quotes.models import Quote
        from apps.sales_orders.models import SalesOrder
        from apps.purchase_orders.models import PurchaseOrder
        from apps.inventory.models import InventoryItem

        rfqs = RFQ.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
        rfq_count = rfqs.count()
        rfq_email = rfqs.filter(source='email').count()
        rfq_manual = rfqs.filter(source='manual').count()
        open_rfqs = RFQ.objects.filter(status='open').count()
        quoted_rfqs = RFQ.objects.filter(status__in=['partially_quoted', 'fully_quoted']).count()

        quotes = Quote.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
        sales_orders = SalesOrder.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
        purchase_orders = PurchaseOrder.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

        total_sales_value = sum(so.total_value for so in sales_orders)
        total_profit = sum(so.total_profit for so in sales_orders)
        total_purchase_value = sum(po.total_cost for po in purchase_orders)

        inventory_value = InventoryItem.objects.filter(item_type='own_stock').aggregate(
            total=Sum('cost')
        )['total'] or 0

        aging_rfqs = RFQ.objects.filter(
            status='open',
            created_at__date__lte=today - timedelta(days=7)
        ).count()

        aging_pos = PurchaseOrder.objects.filter(
            status__in=['sent', 'confirmed'],
            created_at__date__lte=today - timedelta(days=14)
        ).count()

        # Conversion rate
        won_rfqs = rfqs.filter(status='won').count()
        conversion_rate = round(won_rfqs / rfq_count * 100, 1) if rfq_count else 0

    except Exception:
        rfq_count = rfq_email = rfq_manual = open_rfqs = quoted_rfqs = 0
        total_sales_value = total_profit = total_purchase_value = inventory_value = 0
        aging_rfqs = aging_pos = conversion_rate = 0
        quotes = sales_orders = purchase_orders = []

    context = {
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,
        'rfq_count': rfq_count,
        'rfq_email': rfq_email,
        'rfq_manual': rfq_manual,
        'open_rfqs': open_rfqs,
        'quoted_rfqs': quoted_rfqs,
        'conversion_rate': conversion_rate,
        'total_sales_value': total_sales_value,
        'total_profit': total_profit,
        'total_purchase_value': total_purchase_value,
        'inventory_value': inventory_value,
        'aging_rfqs': aging_rfqs,
        'aging_pos': aging_pos,
    }
    return render(request, 'dashboard/dashboard.html', context)
