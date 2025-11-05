# ============================================================
# IMPORTACIONES
# ============================================================
# Importaciones de Python
from django.contrib.auth.models import Group
from decimal import Decimal
import datetime
import csv
import base64
from io import BytesIO

# Importaciones de Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Sum, Case, When, F, Value, DecimalField, Q
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, DetailView, View, UpdateView
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django import forms 

# Importaciones de librerías externas
import pandas as pd
import qrcode
import barcode
from barcode.writer import ImageWriter
from prophet import Prophet
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from thefuzz import process 

# Importaciones de esta app (inventario)
from .models import (
    UnidadMedida, MateriaPrima, MovimientoMP,
    Producto, Receta, RecetaLinea, OrdenProduccion,
    LoteProducto, Venta, VentaLinea, VentaConsumo,
    HistoricoVenta, SuscripcionCliente, User 
)
from .forms import (
    CustomUserCreationForm, 
    MateriaPrimaForm,
    MovimientoIngresoForm, MovimientoAjusteForm, MovimientoMermaForm,
    RecetaForm, RecetaLineaFormSet,
    OrdenProduccionForm,
    VentaForm, VentaLineaFormSet,
    UploadFileForm, 
    UploadInvoiceForm 
)

# ============================================================
# VISTAS PÚBLICAS (LANDING PAGE, REGISTRO, PRECIOS)
# ============================================================

def index(request):
    return render(request, "index.html")

def pagina_precios(request):
    return render(request, "precios.html")


# ============================================================
# VISTAS DE AUTENTICACIÓN (REGISTRO)
# ============================================================

# inventario/views.py

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('inventario:pagina_precios') 

    def form_valid(self, form):
        # 1. Creamos la NUEVA EMPRESA (SuscripcionCliente)
        suscripcion = SuscripcionCliente.objects.create(
            nombre_empresa=f"Empresa de {form.cleaned_data.get('username')}",
            subscription_status='trial' 
        )

        # 2. Guardamos al usuario NUEVO (Dueño)
        usuario = form.save(commit=False)

        # 3. ¡LA CONEXIÓN! Asignamos este usuario a la empresa
        usuario.suscripcion = suscripcion

        # «-- ¡AQUÍ ESTÁ LA CORRECCIÓN! ---
        # 4. Hacemos al usuario "staff" (para que pueda tener permisos)
        usuario.is_staff = True
        usuario.save() # Guardamos el usuario

        # 5. Lo añadimos al grupo "Gerente"
        try:
            gerente_group = Group.objects.get(name='Gerente')
            usuario.groups.add(gerente_group)
        except Group.DoesNotExist:
            # Esto no debería pasar si corriste la migración
            messages.error(self.request, "Error crítico: El grupo 'Gerente' no existe.")
        # --- FIN DE LA CORRECCIÓN ---

        # 6. Asignamos el objeto para que la redirección funcione
        self.object = usuario

        # 7. Iniciamos sesión
        login(self.request, usuario)

        # 8. Redirigimos a la página de precios
        return HttpResponseRedirect(self.get_success_url())
# ============================================================
# VISTAS DE SUSCRIPCIÓN (SIMULACIÓN DE PAGO)
# ============================================================

class SimularSuscripcionView(LoginRequiredMixin, View):
    PLANES = {
        'plan_emprendedor': 'Emprendedor',
        'plan_pro': 'Profesional',
        'plan_empresarial': 'Empresarial',
    }
    def get_plan_info(self, plan_id):
        return self.PLANES.get(plan_id), plan_id in self.PLANES

    def get(self, request, *args, **kwargs):
        plan_id = self.kwargs.get('plan_id')
        plan_nombre, es_valido = self.get_plan_info(plan_id)
        if not es_valido:
            messages.error(request, "El plan seleccionado no es válido.")
            return redirect('inventario:pagina_precios')
        return render(request, "simular_suscripcion.html", {
            "plan_nombre": plan_nombre, "plan_id": plan_id
        })

    def post(self, request, *args, **kwargs):
        plan_id = self.kwargs.get('plan_id')
        plan_nombre, es_valido = self.get_plan_info(plan_id)
        if not es_valido:
            messages.error(request, "El plan seleccionado no es válido.")
            return redirect('inventario:pagina_precios')
        try:
            suscripcion = request.user.suscripcion 
            if suscripcion is None:
                messages.error(request, "No se encontró tu cuenta de empresa. Por favor, contacta a soporte.")
                return redirect('inventario:pagina_precios')
            
            suscripcion.plan_actual = plan_id
            suscripcion.subscription_status = 'active'
            suscripcion.ha_completado_onboarding = False 
            suscripcion.save()
            messages.success(request, f"¡Simulación exitosa! Tu plan ha sido actualizado a '{plan_nombre}'.")
            return redirect('inventario:panel')
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")
            return redirect('inventario:pagina_precios')

@login_required
def ver_suscripcion(request):
    suscripcion = request.user.suscripcion
    if suscripcion is None:
        messages.error(request, "No tienes una suscripción activa.")
        return redirect('inventario:pagina_precios')
    return render(request, "ver_suscripcion.html", {"suscripcion": suscripcion})

# ============================================================
# VISTAS DEL "ONBOARDING WIZARD" (SIMPLIFICADO)
# ============================================================

# «-- ¡BORRADO! La vista 'UnidadCreateView' se eliminó 
#    porque las unidades ahora se cargan desde la migración 0002.

class ProductoCreateView(LoginRequiredMixin, CreateView):
    model = Producto
    fields = ['nombre', 'unidad', 'vida_util_dias'] 
    template_name = "wizard_form_simple.html"
    success_url = reverse_lazy("inventario:wizard_productos")
    extra_context = {"titulo": "Crear Nuevo Producto Terminado"}

    def form_valid(self, form):
        form.instance.suscripcion = self.request.user.suscripcion
        return super().form_valid(form)

# --- Vistas de Pasos del Wizard ---
@login_required
def wizard_bienvenida(request):
    return render(request, "wizard_step_1_bienvenida.html")
    # (Asegúrate que 'wizard_step_1_bienvenida.html' apunte a 'wizard_materias_primas')

# «-- ¡BORRADO! La vista 'wizard_unidades' se eliminó 
#    porque las unidades ahora se cargan desde la migración 0002.

@login_required
def wizard_materias_primas(request):
    materias_primas = MateriaPrima.objects.filter(suscripcion=request.user.suscripcion)
    return render(request, "wizard_step_2_listado.html", {
        "lista_objetos": materias_primas, "titulo": "Materias Primas (Ingredientes)",
        "texto_ayuda": "Ahora, crea tu catálogo de ingredientes (ej. Harina, Levadura).",
        "url_crear": f"{reverse('inventario:mp_create')}?next=wizard",
        "url_siguiente": reverse("inventario:wizard_productos")
    })

@login_required
def wizard_productos(request):
    productos = Producto.objects.filter(suscripcion=request.user.suscripcion)
    return render(request, "wizard_step_2_listado.html", {
        "lista_objetos": productos, "titulo": "Productos Terminados",
        "texto_ayuda": "Crea los productos que vendes (ej. Pan Amasado, Hallulla).",
        "url_crear": reverse("inventario:wizard_crear_producto"),
        "url_siguiente": reverse("inventario:wizard_stock_inicial")
    })

@login_required
def wizard_stock_inicial(request):
    movimientos = MovimientoMP.objects.filter(
        tipo=MovimientoMP.INGRESO, mp__suscripcion=request.user.suscripcion 
    )
    return render(request, "wizard_step_2_listado.html", {
        "lista_objetos": movimientos, "titulo": "Inventario Inicial",
        "texto_ayuda": "¡Casi listos! Ahora registra el stock actual de tus ingredientes.",
        "url_crear": reverse("inventario:mp_ingreso"), 
        "url_siguiente": reverse("inventario:wizard_finalizar")
    })

@login_required
def wizard_finalizar(request):
    if request.method == 'POST':
        try:
            suscripcion = request.user.suscripcion
            if suscripcion:
                suscripcion.ha_completado_onboarding = True; suscripcion.save()
                messages.success(request, "¡Configuración completada! Bienvenido a Ferryx.")
                return redirect('inventario:panel')
            else:
                messages.error(request, "Error: No se encontró tu suscripción.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error: {e}")
    return render(request, "wizard_step_6_finalizar.html")

# ============================================================
# VISTAS CORE DEL ERP (Materias primas / Kardex)
# ============================================================
class MPListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    # (Esta vista y las siguientes están bien, filtran por suscripción)
    permission_required = "inventario.view_materiaprima" 
    model = MateriaPrima; template_name = "mp_list.html"
    context_object_name = "items"; paginate_by = 50
    def get_queryset(self):
        return super().get_queryset().filter(suscripcion=self.request.user.suscripcion)

class MPCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "inventario.add_materiaprima"
    model = MateriaPrima
    form_class = MateriaPrimaForm
    template_name = "mp_form.html" 
    
    # --- ¡AQUÍ ESTÁ LA CORRECCIÓN! ---
    # Este método le dice a Django a dónde ir DESPUÉS de guardar.
    def get_success_url(self):
        # 1. Comprueba si la URL tiene la "pista" ?next=wizard
        if self.request.GET.get('next') == 'wizard':
            # 2. Si la tiene, te devuelve al paso del wizard
            return reverse_lazy("inventario:wizard_materias_primas")
        
        # 3. Si no la tiene (es un usuario normal), te manda a la lista principal
        return reverse_lazy("inventario:mp_list")
    
    # Tu método form_valid está perfecto, se queda igual.
    def form_valid(self, form):
        self.object = form.save(commit=True, user=self.request.user)
        return HttpResponseRedirect(self.get_success_url())

class MPIngresoView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "inventario.add_movimientomp"
    model = MovimientoMP; form_class = MovimientoIngresoForm
    template_name = "mov_form.html"
    
    def get_success_url(self):
        if 'wizard' in self.request.path:
            return reverse_lazy("inventario:wizard_stock_inicial")
        return reverse_lazy("inventario:wizard_stock_inicial")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs(); kwargs['user'] = self.request.user; return kwargs
    def form_valid(self, form):
        form.save(user=self.request.user); messages.success(self.request, "Ingreso registrado.")
        return redirect(self.get_success_url())

class MPAjusteView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "inventario.add_movimientomp"
    model = MovimientoMP; form_class = MovimientoAjusteForm
    template_name = "mov_form.html"; success_url = reverse_lazy("inventario:kardex")
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs(); kwargs['user'] = self.request.user; return kwargs
    def form_valid(self, form):
        form.save(user=self.request.user); messages.success(self.request, "Ajuste registrado.")
        return redirect(self.success_url)

class MPMermaView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "inventario.add_movimientomp"
    model = MovimientoMP; form_class = MovimientoMermaForm
    template_name = "mov_form.html"; success_url = reverse_lazy("inventario:kardex")
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs(); kwargs['user'] = self.request.user; return kwargs
    def form_valid(self, form):
        form.save(user=self.request.user); messages.success(self.request, "Merma registrada.")
        return redirect(self.success_url)

@login_required
@permission_required("inventario.view_movimientomp", raise_exception=True)
def kardex(request):
    qs = MovimientoMP.objects.filter(
        mp__suscripcion=request.user.suscripcion
    ).select_related("mp").order_by("-fecha")[:300]
    return render(request, "kardex.html", {"movs": qs})

# ============================================================
# VISTAS CORE DEL ERP (Recetas)
# ============================================================
class RecetaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_receta" 
    model = Receta; template_name = "receta_list.html"
    context_object_name = "recetas"; paginate_by = 50
    def get_queryset(self):
        suscripcion = self.request.user.suscripcion
        qs = (Receta.objects
            .filter(producto__suscripcion=suscripcion)
            .select_related("producto").prefetch_related("lineas__mp")
            .order_by("producto__nombre", "nombre", "-version"))
        q = self.request.GET.get("q")
        if q: qs = qs.filter(Q(producto__nombre__icontains=q) | Q(nombre__icontains=q))
        return qs

class RecetaCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "inventario.add_receta"; template_name = "receta_form.html"
    def get(self, request):
        form = RecetaForm(user=request.user)
        formset = RecetaLineaFormSet(form_kwargs={'user': request.user})
        return render(request, self.template_name, {"form": form, "formset": formset})
    def post(self, request):
        form = RecetaForm(request.POST, user=request.user)
        formset = RecetaLineaFormSet(request.POST, form_kwargs={'user': request.user})
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, {"form": form, "formset": formset})
        with transaction.atomic():
            receta = form.save(); formset.instance = receta; formset.save() 
        messages.success(request, "Receta creada correctamente.")
        return redirect("inventario:receta_detail", pk=receta.pk)

class RecetaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "inventario.change_receta"; template_name = "receta_form.html"
    def get(self, request, pk):
        receta = get_object_or_404(Receta, pk=pk, producto__suscripcion=request.user.suscripcion)
        form = RecetaForm(instance=receta, user=request.user)
        formset = RecetaLineaFormSet(instance=receta, form_kwargs={'user': request.user})
        return render(request, self.template_name, {"form": form, "formset": formset, "obj": receta})
    def post(self, request, pk):
        receta = get_object_or_404(Receta, pk=pk, producto__suscripcion=request.user.suscripcion)
        form = RecetaForm(request.POST, instance=receta, user=request.user)
        formset = RecetaLineaFormSet(request.POST, instance=receta, form_kwargs={'user': request.user})
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, {"form": form, "formset": formset, "obj": receta})
        with transaction.atomic():
            receta = form.save(); formset.save()
        messages.success(request, "Receta actualizada.")
        return redirect("inventario:receta_detail", pk=receta.pk)

class RecetaDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventario.view_receta" 
    model = Receta; template_name = "receta_detail.html"
    context_object_name = "receta"
    def get_queryset(self):
        return super().get_queryset().filter(producto__suscripcion=self.request.user.suscripcion)

# ============================================================
# VISTAS CORE DEL ERP (Producción)
# ============================================================
class OPListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_ordenproduccion" 
    model = OrdenProduccion; template_name = "op_list.html"
    context_object_name = "ops"; paginate_by = 50
    def get_queryset(self):
        return super().get_queryset().filter(producto__suscripcion=self.request.user.suscripcion)

class OPCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "inventario.add_ordenproduccion"
    template_name = "op_form.html"; success_url = reverse_lazy("inventario:op_list")
    def get(self, request):
        form = OrdenProduccionForm(user=request.user)
        return render(request, self.template_name, {"form": form})
    def post(self, request):
        form = OrdenProduccionForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        op = form.save(commit=False); op.created_by = request.user; op.save() 
        if form.cleaned_data.get("confirmar_y_ejecutar"):
            try:
                with transaction.atomic():
                    op.validar_stock(); op.ejecutar(user=request.user)
                messages.success(request, "OP creada y ejecutada; lote generado.")
            except Exception as e:
                messages.error(request, f"No se pudo ejecutar la OP: {e}")
        else:
            messages.success(request, "OP creada en estado BORRADOR.")
        return redirect(self.success_url)

class OPDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventario.view_ordenproduccion" 
    model = OrdenProduccion; template_name = "op_detail.html"
    context_object_name = "op"
    def get_queryset(self):
        return super().get_queryset().filter(producto__suscripcion=self.request.user.suscripcion)

# ============================================================
# VISTAS CORE DEL ERP (Lotes)
# ============================================================
class LoteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_loteproducto" 
    model = LoteProducto; template_name = "lote_list.html"
    context_object_name = "lotes"; paginate_by = 50
    def get_queryset(self):
        suscripcion = self.request.user.suscripcion
        qs = super().get_queryset().filter(producto__suscripcion=suscripcion).select_related("producto")
        estado = self.request.GET.get("estado")
        if estado in [LoteProducto.OK, LoteProducto.POR_RALLAR, LoteProducto.VENCIDO]:
            qs = qs.filter(estado=estado)
        q = self.request.GET.get("q")
        if q: qs = qs.filter(Q(producto__nombre__icontains=q) | Q(codigo__icontains=q))
        return qs.order_by("fecha_vencimiento", "created_at")

class LoteDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventario.view_loteproducto" 
    model = LoteProducto; template_name = "lote_detail.html"
    context_object_name = "lote"
    def get_queryset(self):
        return super().get_queryset().filter(producto__suscripcion=self.request.user.suscripcion)

# ============================================================
# VISTAS CORE DEL ERP (Ventas)
# ============================================================
class VentaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_venta" 
    model = Venta; template_name = "venta_list.html"
    context_object_name = "ventas"; paginate_by = 50
    def get_queryset(self):
        return super().get_queryset().filter(suscripcion=self.request.user.suscripcion)

class VentaDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "inventario.view_venta" 
    model = Venta; template_name = "venta_detail.html"
    context_object_name = "venta"
    def get_queryset(self):
        return (super().get_queryset()
            .filter(suscripcion=self.request.user.suscripcion)
            .prefetch_related("lineas__producto", "consumos__lote__producto"))
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lotes_consumidos = []
        for c in self.object.consumos.all():
            codigo = c.lote.codigo; qr_img = qrcode.make(codigo)
            buffer_qr = BytesIO(); qr_img.save(buffer_qr, format="PNG")
            qr_base64 = base64.b64encode(buffer_qr.getvalue()).decode("utf-8")
            CODE128 = barcode.get_barcode_class("code128")
            code128 = CODE128(codigo, writer=ImageWriter())
            buffer_bar = BytesIO(); code128.write(buffer_bar)
            bar_base64 = base64.b64encode(buffer_bar.getvalue()).decode("utf-8")
            lotes_consumidos.append({
                "codigo": codigo, "producto": c.lote.producto.nombre,
                "cantidad": c.cantidad_fmt, "vence": c.lote.fecha_vencimiento,
                "qr": qr_base64, "barcode": bar_base64,
            })
        context["lotes_consumidos"] = lotes_consumidos
        return context

class VentaCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "inventario.add_venta"; template_name = "venta_form.html"
    def get(self, request):
        form = VentaForm(user=request.user)
        formset = VentaLineaFormSet(form_kwargs={'user': request.user})
        return render(request, self.template_name, {"form": form, "formset": formset})
    def post(self, request):
        form = VentaForm(request.POST, user=request.user)
        formset = VentaLineaFormSet(request.POST, form_kwargs={'user': request.user})
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, {"form": form, "formset": formset})
        venta = form.save(commit=False, user=request.user)
        venta.created_by = request.user; venta.save()
        formset.instance = venta
        lines = [ln for ln in formset.save(commit=False) if ln.producto_id and ln.cantidad and Decimal(ln.cantidad) > 0]
        for ln in lines: ln.venta = venta; ln.save()
        for f in formset.deleted_forms:
            if f.instance.pk: f.instance.delete()
        if form.cleaned_data.get("confirmar_y_consumir"):
            try:
                with transaction.atomic():
                    venta.validar_stock(); venta.consumir_fifo(user=request.user)
                messages.success(request, "Venta confirmada y stock descontado (FEFO).")
            except Exception as e:
                messages.error(request, f"No se pudo confirmar: {e}")
                form = VentaForm(instance=venta, user=request.user)
                formset = VentaLineaFormSet(instance=venta, form_kwargs={'user': request.user})
                return render(request, self.template_name, {"form": form, "formset": formset})
        else:
            messages.success(request, "Venta guardada como borrador.")
        return redirect("inventario:venta_detail", pk=venta.pk)

# ============================================================
# VISTAS DE DASHBOARD Y REPORTES
# ============================================================
def _parse_date(s):
    if not s: return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(s, fmt).date()
        except ValueError: pass
    return None

@login_required
def panel(request):
    suscripcion = request.user.suscripcion
    if not suscripcion:
        return render(request, "panel_sin_suscripcion.html") 
    hoy = timezone.localdate()
    desde = _parse_date(request.GET.get("desde")) or hoy
    hasta = _parse_date(request.GET.get("hasta")) or hoy
    start = timezone.make_aware(datetime.datetime.combine(desde, datetime.time.min))
    end   = timezone.make_aware(datetime.datetime.combine(hasta, datetime.time.max))

    ventas_rng = Venta.objects.filter(suscripcion=suscripcion, fecha__range=(start, end))
    ventas_por_producto_qs = (
        VentaLinea.objects.filter(venta__in=ventas_rng)
        .values("producto__nombre")
        .annotate(total=Coalesce(Sum("cantidad"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=3)))
        .order_by("producto__nombre")
    )
    total_unidades_vendidas = (
        VentaLinea.objects.filter(venta__in=ventas_rng)
        .aggregate(total=Coalesce(Sum("cantidad"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=3)))["total"]
    )
    total_ventas = ventas_rng.count()
    ops_rng = OrdenProduccion.objects.filter(producto__suscripcion=suscripcion, fecha__range=(start, end))
    unidades_producidas = sum([op.unidades_totales for op in ops_rng])
    mm = MovimientoMP
    mermas_mp_qs = (
        MovimientoMP.objects.filter(mp__suscripcion=suscripcion, tipo=mm.MERMA, fecha__range=(start, end))
        .values("mp__nombre")
        .annotate(total=Coalesce(Sum("cantidad"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=3)))
        .order_by("mp__nombre")
    )
    total_mermas_mp = (
        MovimientoMP.objects.filter(mp__suscripcion=suscripcion, tipo=mm.MERMA, fecha__range=(start, end))
        .aggregate(total=Coalesce(Sum("cantidad"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=3)))["total"]
    )
    mp_alertas = (
        MateriaPrima.objects.filter(suscripcion=suscripcion, stock__lte=F("stock_minimo")).order_by("nombre")
    )
    hoy_date = hoy
    lotes_por_vencer = LoteProducto.objects.filter(
        producto__suscripcion=suscripcion, fecha_vencimiento__gte=hoy_date,
        fecha_vencimiento__lte=hoy_date + datetime.timedelta(days=1),
        cantidad_disponible__gt=0,
    ).order_by("fecha_vencimiento", "created_at")
    lotes_vencidos = LoteProducto.objects.filter(
        producto__suscripcion=suscripcion, fecha_vencimiento__lt=hoy_date,
        cantidad_disponible__gt=0,
    ).order_by("fecha_vencimiento", "created_at")
    chart_prod_labels = [r["producto__nombre"] for r in ventas_por_producto_qs]
    chart_prod_values = [float(r["total"]) for r in ventas_por_producto_qs]
    inicio_7 = hoy - datetime.timedelta(days=6)
    ventas_7 = (
        Venta.objects.filter(
            suscripcion=suscripcion, fecha__date__gte=inicio_7, fecha__date__lte=hoy
        ).annotate(d=TruncDate("fecha")).values("d")
        .annotate(unidades=Coalesce(Sum("lineas__cantidad"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=3)))
        .order_by("d")
    )
    serie_7 = {v["d"]: float(v["unidades"]) for v in ventas_7}
    chart_7_labels, chart_7_values = [], [],
    for i in range(7):
        d = inicio_7 + datetime.timedelta(days=i)
        chart_7_labels.append(d.strftime("%d-%m"))
        chart_7_values.append(serie_7.get(d, 0.0))
    context = {
        "desde": desde, "hasta": hasta, "total_ventas": total_ventas,
        "total_unidades_vendidas": total_unidades_vendidas,
        "ventas_por_producto": list(ventas_por_producto_qs),
        "ops_hoy": ops_rng, "unidades_producidas_hoy": unidades_producidas,
        "mermas_mp_hoy": list(mermas_mp_qs), "total_mermas_mp_hoy": total_mermas_mp,
        "mp_alertas": mp_alertas, "lotes_por_vencer": lotes_por_vencer,
        "lotes_vencidos": lotes_vencidos, "chart_prod_labels": chart_prod_labels,
        "chart_prod_values": chart_prod_values, "chart_7_labels": chart_7_labels,
        "chart_7_values": chart_7_values,
    }
    return render(request, "panel.html", context)

@login_required
@permission_required("inventario.view_venta", raise_exception=True)
def panel_csv(request):
    suscripcion = request.user.suscripcion
    if not suscripcion:
        return HttpResponse("No tiene una suscripción asociada.", status=403)
    hoy = timezone.localdate()
    desde = _parse_date(request.GET.get("desde")) or hoy
    hasta = _parse_date(request.GET.get("hasta")) or hoy
    start = timezone.make_aware(datetime.datetime.combine(desde, datetime.time.min))
    end   = timezone.make_aware(datetime.datetime.combine(hasta, datetime.time.max))
    ventas_rng = Venta.objects.filter(suscripcion=suscripcion, fecha__range=(start, end))
    ventas_por_producto = (
        VentaLinea.objects.filter(venta__in=ventas_rng)
        .values("producto__nombre")
        .annotate(total=Coalesce(Sum("cantidad"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=3)))
        .order_by("producto__nombre")
    )
    total_unidades_vendidas = (
        VentaLinea.objects.filter(venta__in=ventas_rng)
        .aggregate(total=Coalesce(Sum("cantidad"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=3)))["total"]
    )
    filename = f"reporte_{desde.strftime('%Y%m%d')}_{hasta.strftime('%Y%m%d')}.csv"
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    w = csv.writer(resp); w.writerow(["Desde", desde.isoformat(), "Hasta", hasta.isoformat()])
    w.writerow([]); w.writerow(["Producto", "Unidades vendidas"])
    for r in ventas_por_producto: w.writerow([r["producto__nombre"], r["total"]])
    w.writerow([]); w.writerow(["Total unidades", total_unidades_vendidas])
    return resp

# ============================================================
# VISTAS DE IA E INTEGRACIONES
# ============================================================
class CargarExcelVentasView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "inventario.can_run_predictions" 
    template_name = "cargar_excel.html"
    def get(self, request):
        return render(request, self.template_name)
    def post(self, request):
        suscripcion = request.user.suscripcion
        if not suscripcion:
            messages.error(request, "No tienes una suscripción activa.")
            return redirect("inventario:panel")
        excel_file = request.FILES["file"]
        fs = FileSystemStorage(); filename = fs.save(excel_file.name, excel_file)
        file_path = fs.path(filename); df = pd.read_excel(file_path)
        for _, row in df.iterrows():
            unidad_default = UnidadMedida.objects.filter(nombre__iexact='kg').first()
            if not unidad_default: unidad_default = UnidadMedida.objects.first()
            prod, _ = Producto.objects.get_or_create(
                suscripcion=suscripcion, nombre=row["producto"],
                defaults={'unidad': unidad_default}
            )
            HistoricoVenta.objects.create(
                suscripcion=suscripcion, fecha=row["fecha"],
                producto=prod, cantidad=row["cantidad"]
            )
        return redirect("inventario:predict")

@login_required
@permission_required("inventario.can_run_predictions", raise_exception=True)
def predict_view(request):
    context = {}
    if request.method == "POST":
        messages.warning(request, "La predicción aún no está conectada a la base de datos.")
        pass
    context["form"] = UploadFileForm()
    return render(request, "predict.html", context)

@login_required
@permission_required("inventario.add_movimientomp", raise_exception=True)
def procesar_factura(request):
    suscripcion = request.user.suscripcion
    if not suscripcion:
        messages.error(request, "No tienes una suscripción activa.")
        return redirect("inventario:panel")
    endpoint = settings.AZURE_DOCINT_ENDPOINT
    key = AzureKeyCredential(settings.AZURE_DOCINT_KEY)
    document_analysis_client = DocumentAnalysisClient(endpoint, key)
    todas_las_mps = MateriaPrima.objects.filter(suscripcion=suscripcion, activo=True)
    opciones_mps = [mp.nombre for mp in todas_las_mps] 
    if not opciones_mps:
        messages.warning(request, "No tienes materias primas cargadas para comparar.")
    if request.method == "POST":
        form = UploadInvoiceForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['invoice_file']
            file_content = uploaded_file.read()
            poller = document_analysis_client.begin_analyze_document("prebuilt-invoice", file_content)
            result = poller.result()
            items_a_confirmar = []
            if result.documents:
                document = result.documents[0]
                items_field = document.fields.get("Items")
                if items_field and items_field.value:
                    for item in items_field.value:
                        descripcion = item.value.get("Description")
                        cantidad = item.value.get("Quantity")
                        if not descripcion or not cantidad or not opciones_mps: continue
                        try:
                            mejor_coincidencia = process.extractOne(descripcion.value, opciones_mps)
                            mp_sugerida = todas_las_mps.get(nombre=mejor_coincidencia[0])
                            items_a_confirmar.append({
                                'azure_desc': descripcion.value,
                                'azure_qty': cantidad.value,
                                'sugerencia_id': mp_sugerida.id,
                            })
                        except Exception: pass
            context = {
                'form': form, 'items_a_confirmar': items_a_confirmar,
                'todas_las_mps': todas_las_mps,
            }
            return render(request, "invoice_confirm.html", context)
    else:
        form = UploadInvoiceForm()
    return render(request, "invoice_upload.html", {'form': form})

@login_required
@permission_required("inventario.add_movimientomp", raise_exception=True)
@transaction.atomic
def guardar_ingreso_factura(request):
    suscripcion = request.user.suscripcion
    if not suscripcion:
        messages.error(request, "No tienes una suscripción activa.")
        return redirect("inventario:panel")
    if request.method != "POST":
        return redirect("inventario:panel")
    try:
        item_count = int(request.POST.get('item_count', 0)); items_creados = 0
        mps_permitidas = set(
            MateriaPrima.objects.filter(suscripcion=suscripcion).values_list('id', flat=True)
        )
        for i in range(item_count):
            mp_id_str = request.POST.get(f'item-{i}-mp'); cantidad = request.POST.get(f'item-{i}-qty')
            if not mp_id_str or not cantidad: continue
            mp_id = int(mp_id_str)
            if mp_id not in mps_permitidas:
                messages.warning(request, f"Se ignoró un item ({mp_id}) que no pertenece a tu empresa.")
                continue
            if mp_id and cantidad and float(cantidad.replace(",", ".")) > 0:
                azure_desc = request.POST.get(f'item-{i}-azure_desc')
                MovimientoMP.objects.create(
                    mp_id=mp_id, tipo=MovimientoMP.INGRESO,
                    cantidad=Decimal(cantidad.replace(",", ".")),
                    nota=f"Ingreso por factura: {azure_desc}",
                    created_by=request.user
                )
                items_creados += 1
        messages.success(request, f"¡Ingreso de stock guardado! Se crearon {items_creados} movimientos.")
    except Exception as e:
        messages.error(request, f"Error al guardar el ingreso: {e}")
    return redirect("inventario:kardex")