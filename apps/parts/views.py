from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
import csv
from io import TextIOWrapper
from .models import Part


@login_required
def part_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', 'active')
    parts = Part.objects.all()
    if q:
        parts = parts.filter(Q(part_number__icontains=q) | Q(description__icontains=q) | Q(manufacturer__icontains=q))
    if status:
        parts = parts.filter(status=status)
    paginator = Paginator(parts, 50)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'parts/list.html', {'page': page, 'q': q, 'status': status})


@login_required
def part_create(request):
    if request.method == 'POST':
        part = Part(
            part_number=request.POST['part_number'],
            manufacturer=request.POST.get('manufacturer', ''),
            manufacturer_code=request.POST.get('manufacturer_code', ''),
            description=request.POST.get('description', ''),
            uom=request.POST.get('uom', 'EA'),
            condition=request.POST.get('condition', ''),
            is_hazardous=request.POST.get('is_hazardous') == 'on',
            alternate_pn=request.POST.get('alternate_pn', ''),
            superseded_pn=request.POST.get('superseded_pn', ''),
            internal_notes=request.POST.get('internal_notes', ''),
            tags=request.POST.get('tags', ''),
            status=request.POST.get('status', 'active'),
            created_by=request.user,
        )
        try:
            part.save()
            messages.success(request, f'Part {part.part_number} created successfully.')
            return redirect('part_list')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return render(request, 'parts/form.html', {'action': 'Create', 'part': None})


@login_required
def part_edit(request, pk):
    part = get_object_or_404(Part, pk=pk)
    if request.method == 'POST':
        part.manufacturer = request.POST.get('manufacturer', '')
        part.manufacturer_code = request.POST.get('manufacturer_code', '')
        part.description = request.POST.get('description', '')
        part.uom = request.POST.get('uom', 'EA')
        part.condition = request.POST.get('condition', '')
        part.is_hazardous = request.POST.get('is_hazardous') == 'on'
        part.alternate_pn = request.POST.get('alternate_pn', '')
        part.superseded_pn = request.POST.get('superseded_pn', '')
        part.internal_notes = request.POST.get('internal_notes', '')
        part.tags = request.POST.get('tags', '')
        part.status = request.POST.get('status', 'active')
        part.save()
        messages.success(request, 'Part updated successfully.')
        return redirect('part_list')
    return render(request, 'parts/form.html', {'action': 'Edit', 'part': part})


@login_required
def part_detail(request, pk):
    part = get_object_or_404(Part, pk=pk)
    return render(request, 'parts/detail.html', {'part': part})


@login_required
def part_bulk_upload(request):
    if request.method == 'POST' and request.FILES.get('file'):
        f = TextIOWrapper(request.FILES['file'].file, encoding='utf-8')
        reader = csv.DictReader(f)
        created, errors = 0, []
        for row in reader:
            try:
                Part.objects.update_or_create(
                    part_number=row['part_number'],
                    defaults={
                        'manufacturer': row.get('manufacturer', ''),
                        'description': row.get('description', ''),
                        'uom': row.get('uom', 'EA'),
                        'status': 'active',
                        'created_by': request.user,
                    }
                )
                created += 1
            except Exception as e:
                errors.append(str(e))
        messages.success(request, f'{created} parts imported. {len(errors)} errors.')
        return redirect('part_list')
    return render(request, 'parts/bulk_upload.html')


@login_required
def part_search_api(request):
    q = request.GET.get('q', '')
    parts = Part.objects.filter(
        Q(part_number__icontains=q) | Q(description__icontains=q), status='active'
    )[:20]
    data = [{'id': p.id, 'part_number': p.part_number, 'description': p.description} for p in parts]
    return JsonResponse({'results': data})
