from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from .models import Company, Contact


@login_required
def company_list(request):
    q = request.GET.get('q', '')
    company_type = request.GET.get('type', '')
    companies = Company.objects.filter(is_active=True)
    if q:
        companies = companies.filter(Q(name__icontains=q) | Q(tax_id__icontains=q))
    if company_type:
        companies = companies.filter(company_type=company_type)
    paginator = Paginator(companies, 50)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'companies/list.html', {'page': page, 'q': q, 'type': company_type})


@login_required
def company_create(request):
    if request.method == 'POST':
        company = Company(
            name=request.POST['name'],
            company_type=request.POST.get('company_type', 'customer'),
            billing_address=request.POST.get('billing_address', ''),
            shipping_address=request.POST.get('shipping_address', ''),
            payment_terms=request.POST.get('payment_terms', ''),
            tax_id=request.POST.get('tax_id', ''),
            default_currency=request.POST.get('default_currency', 'USD'),
            credit_limit=request.POST.get('credit_limit') or None,
            internal_notes=request.POST.get('internal_notes', ''),
        )
        company.save()
        messages.success(request, f'Company {company.name} created.')
        return redirect('company_list')
    return render(request, 'companies/form.html', {'action': 'Create', 'company': None})


@login_required
def company_edit(request, pk):
    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        company.name = request.POST['name']
        company.company_type = request.POST.get('company_type', 'customer')
        company.billing_address = request.POST.get('billing_address', '')
        company.shipping_address = request.POST.get('shipping_address', '')
        company.payment_terms = request.POST.get('payment_terms', '')
        company.tax_id = request.POST.get('tax_id', '')
        company.default_currency = request.POST.get('default_currency', 'USD')
        company.credit_limit = request.POST.get('credit_limit') or None
        company.internal_notes = request.POST.get('internal_notes', '')
        company.save()
        messages.success(request, 'Company updated.')
        return redirect('company_detail', pk=pk)
    return render(request, 'companies/form.html', {'action': 'Edit', 'company': company})


@login_required
def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk)
    contacts = company.contacts.all()
    return render(request, 'companies/detail.html', {'company': company, 'contacts': contacts})


@login_required
def contact_add(request, company_pk):
    company = get_object_or_404(Company, pk=company_pk)
    if request.method == 'POST':
        Contact.objects.create(
            company=company,
            first_name=request.POST['first_name'],
            last_name=request.POST.get('last_name', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            title=request.POST.get('title', ''),
            is_primary=request.POST.get('is_primary') == 'on',
        )
        messages.success(request, 'Contact added.')
    return redirect('company_detail', pk=company_pk)


@login_required
def company_search_api(request):
    q = request.GET.get('q', '')
    company_type = request.GET.get('type', '')
    companies = Company.objects.filter(name__icontains=q, is_active=True)
    if company_type:
        companies = companies.filter(company_type__in=[company_type, 'both'])
    companies = companies[:20]
    data = [{'id': c.id, 'name': c.name, 'type': c.company_type} for c in companies]
    return JsonResponse({'results': data})
