from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from monitoring.models import Monitor
from products.models import Product
from products.services.database import clear_scraped_data

SORT_OPTIONS = {
    "discount_desc": {"label": "Descuento (mayor)", "needs_price": False},
    "updated_desc": {"label": "Actualización (reciente)", "needs_price": False},
    "updated_asc": {"label": "Actualización (antigua)", "needs_price": False},
    "price_asc": {"label": "Precio (menor a mayor)", "needs_price": True},
    "price_desc": {"label": "Precio (mayor a menor)", "needs_price": True},
    "name_asc": {"label": "Nombre (A-Z)", "needs_price": False},
    "name_desc": {"label": "Nombre (Z-A)", "needs_price": False},
    "rating_desc": {"label": "Rating (mayor)", "needs_price": False},
    "rating_asc": {"label": "Rating (menor)", "needs_price": False},
    "retail_asc": {"label": "Tienda (A-Z)", "needs_price": False},
}

DEFAULT_SORT = "discount_desc"


def _apply_sorting(queryset, sort):
    if sort == "price_asc":
        return queryset.order_by(F("price_best").asc(nulls_last=True), "name")
    if sort == "price_desc":
        return queryset.order_by(F("price_best").desc(nulls_last=True), "name")
    if sort == "updated_asc":
        return queryset.order_by("updated_at")
    if sort == "name_asc":
        return queryset.order_by("name")
    if sort == "name_desc":
        return queryset.order_by("-name")
    if sort == "rating_asc":
        return queryset.order_by(F("rating").asc(nulls_last=True), "name")
    if sort == "rating_desc":
        return queryset.order_by(F("rating").desc(nulls_last=True), "name")
    if sort == "retail_asc":
        return queryset.order_by("seller", "name")
    if sort == "discount_desc":
        return queryset.order_by(F("discount_percent").desc(nulls_last=True), "name")
    if sort == "updated_desc":
        return queryset.order_by("-updated_at")
    return queryset.order_by(F("discount_percent").desc(nulls_last=True), "name")


def _build_query_string(get_params, page=None):
    params = get_params.copy()
    params.pop("page", None)
    if page is not None:
        params["page"] = str(page)
    return params.urlencode()


@login_required
def dashboard(request):
    total_products = Product.objects.count()
    total_monitors = Monitor.objects.count()
    last_update = Product.objects.aggregate(last=Max("updated_at"))["last"]
    active_monitors = Monitor.objects.filter(active=True).count()
    recent_products = Product.objects.all()[:5]
    total_retailers = (
        Product.objects.exclude(retail="").values("retail").distinct().count()
    )

    context = {
        "total_products": total_products,
        "total_monitors": total_monitors,
        "active_monitors": active_monitors,
        "total_retailers": total_retailers,
        "last_update": last_update or timezone.now(),
        "recent_products": recent_products,
    }
    return render(request, "products/dashboard.html", context)


@login_required
def product_list(request):
    queryset = Product.objects.all()
    q = request.GET.get("q", "").strip()
    exclude_q = request.GET.get("exclude", "").strip()
    brand = request.GET.get("brand", "").strip()
    retail = request.GET.get("retail", "").strip()
    price_min = request.GET.get("price_min", "").strip()
    price_max = request.GET.get("price_max", "").strip()
    sort = request.GET.get("sort", DEFAULT_SORT)
    if sort not in SORT_OPTIONS:
        sort = DEFAULT_SORT

    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(brand__icontains=q)
            | Q(seller__icontains=q)
            | Q(retail__icontains=q)
            | Q(kid__icontains=q)
            | Q(product_id__icontains=q)
        )

    if exclude_q:
        queryset = queryset.exclude(
            Q(name__icontains=exclude_q)
            | Q(brand__icontains=exclude_q)
            | Q(seller__icontains=exclude_q)
            | Q(retail__icontains=exclude_q)
            | Q(kid__icontains=exclude_q)
            | Q(product_id__icontains=exclude_q)
        )

    if brand:
        queryset = queryset.filter(brand__iexact=brand)

    if retail:
        queryset = queryset.filter(retail__iexact=retail)

    if price_min.isdigit():
        queryset = queryset.filter(price_best__gte=int(price_min))
    if price_max.isdigit():
        queryset = queryset.filter(price_best__lte=int(price_max))

    queryset = _apply_sorting(queryset, sort)

    paginator = Paginator(queryset, 24)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    brands = (
        Product.objects.exclude(brand="")
        .values_list("brand", flat=True)
        .distinct()
        .order_by("brand")
    )
    retails = (
        Product.objects.exclude(retail="")
        .values_list("retail", flat=True)
        .distinct()
        .order_by("retail")
    )

    has_filters = any(
        [q, exclude_q, brand, retail, price_min, price_max, sort != DEFAULT_SORT]
    )

    return render(
        request,
        "products/product_list.html",
        {
            "page_obj": page_obj,
            "q": q,
            "exclude_q": exclude_q,
            "brand": brand,
            "retail": retail,
            "price_min": price_min,
            "price_max": price_max,
            "sort": sort,
            "sort_options": SORT_OPTIONS,
            "brands": brands,
            "retails": retails,
            "has_filters": has_filters,
            "query_string": _build_query_string(request.GET),
            "prev_query": _build_query_string(
                request.GET, page_obj.previous_page_number()
            )
            if page_obj.has_previous()
            else "",
            "next_query": _build_query_string(request.GET, page_obj.next_page_number())
            if page_obj.has_next()
            else "",
        },
    )


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    history = product.price_history.all()[:50]
    return render(
        request,
        "products/product_detail.html",
        {"product": product, "history": history},
    )


@login_required
@require_POST
def clear_data(request):
    stats = clear_scraped_data()
    messages.success(
        request,
        f"Datos eliminados: {stats['products']} productos, "
        f"{stats['history']} registros de historial, "
        f"{stats['monitors']} monitores. Los usuarios no fueron afectados.",
    )
    return redirect("dashboard")
