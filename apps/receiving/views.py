from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import GoodsReceiptNote, GRNLine
from apps.purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from apps.inventory.models import InventoryItem


@login_required
def receiving_list(request):
    open_pos = PurchaseOrder.objects.filter(
        status__in=['confirmed', 'partially_received']
    ).select_related('vendor').all()
    grns = GoodsReceiptNote.objects.select_related('purchase_order__vendor').all()[:50]
    return render(request, 'receiving/list.html', {'open_pos': open_pos, 'grns': grns})


@login_required
def receive_po(request, po_pk):
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    lines = po.lines.select_related('part').all()

    if request.method == 'POST':
        grn = GoodsReceiptNote(
            purchase_order=po,
            received_by=request.user,
            quality_check_passed=request.POST.get('quality_check') == 'on',
            quality_notes=request.POST.get('quality_notes', ''),
            notes=request.POST.get('notes', ''),
        )
        grn.save()

        all_received = True
        for line in lines:
            qty_key = f'qty_{line.pk}'
            qty = request.POST.get(qty_key)
            if qty:
                qty = float(qty)
                GRNLine.objects.create(
                    grn=grn,
                    po_line=line,
                    quantity_received=qty,
                    quality_ok=request.POST.get(f'qc_{line.pk}') == 'on',
                )
                line.quantity_received += qty
                line.save()

                # Update inventory
                if line.part:
                    InventoryItem.objects.create(
                        item_type='own_stock',
                        part=line.part,
                        description=line.description,
                        quantity=qty,
                        quantity_available=qty,
                        cost=line.cost,
                        currency=po.currency,
                        linked_po=po,
                        created_by=request.user,
                    )

            if line.quantity_received < line.quantity:
                all_received = False

        if all_received:
            po.status = 'fully_received'
        else:
            po.status = 'partially_received'
        po.save()

        messages.success(request, f'GRN {grn.grn_number} created. Inventory updated.')
        return redirect('receiving_list')
    return render(request, 'receiving/receive_po.html', {'po': po, 'lines': lines})
