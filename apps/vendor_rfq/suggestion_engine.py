from collections import defaultdict
from .models import VendorRFQLine, VendorSuggestionLog
from apps.companies.models import Company


def get_vendor_suggestions(inquiry):
    """
    Returns:
        suggested: dict { vendor_id: set(part_numbers) }  — vendors with a match signal
        all_vendors: queryset of all active vendors
        reasons: dict { (vendor_id, part_number): reason_label }
    """
    suggested  = defaultdict(set)
    reasons    = {}
    part_numbers = [l.part_number_raw for l in inquiry.lines.all()]

    for line in inquiry.lines.all():
        pn = line.part_number_raw

        # Signal 1: vendors who previously quoted this exact PN and got a quote back
        past = VendorRFQLine.objects.filter(
            part_number__iexact=pn,
            vendor_rfq__status__in=['quoted', 'won'],
        ).select_related('vendor_rfq__vendor')

        for vrfq_line in past:
            vid = vrfq_line.vendor_rfq.vendor_id
            suggested[vid].add(pn)
            reasons[(vid, pn)] = VendorSuggestionLog.REASON_QUOTE_HISTORY

        # Signal 2: vendors who stock this PN in inventory
        # Adjust the import path + field names to your inventory model
        try:
            from apps.inventory.models import InventoryItem
            stocking = InventoryItem.objects.filter(
                part__part_number__iexact=pn,
                quantity__gt=0,
            ).values_list('vendor_id', flat=True)  # adjust if field name differs
            for vid in stocking:
                if vid:
                    suggested[vid].add(pn)
                    if (vid, pn) not in reasons:
                        reasons[(vid, pn)] = VendorSuggestionLog.REASON_INVENTORY
        except Exception:
            pass  # inventory app may not exist yet — safe to skip

        # Signal 3: vendors tagged with a matching part category
        # (placeholder — wire up when you have vendor-category tagging)
        # ...

    all_vendors = Company.objects.filter(
        company_type__in=['vendor', 'both'], is_active=True
    ).order_by('name')

    # If nothing was suggested, flag as fallback
    if not suggested:
        for v in all_vendors:
            for pn in part_numbers:
                reasons[(v.id, pn)] = VendorSuggestionLog.REASON_FALLBACK

    return suggested, all_vendors, reasons


def save_suggestion_log(inquiry, suggested, reasons):
    """Persist suggestion reasons for audit trail."""
    logs = []
    for (vendor_id, pn), reason in reasons.items():
        logs.append(VendorSuggestionLog(
            inquiry=inquiry,
            vendor_id=vendor_id,
            part_number=pn,
            reason=reason,
        ))
    VendorSuggestionLog.objects.bulk_create(logs, ignore_conflicts=True)