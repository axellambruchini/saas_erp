# ============================================================
#  IMPORTACIONES
# ============================================================
from decimal import Decimal, ROUND_HALF_UP 
from datetime import timedelta 
from django.db import models, transaction 
from django.core.exceptions import ValidationError 
from django.utils import timezone
from django.conf import settings 
# «-- ¡CAMBIO IMPORTANTE! Importamos Group y Permission
from django.contrib.auth.models import AbstractUser, Group, Permission

# -----------------------------------------------------------------
# MODELO 1: LA EMPRESA (EL "DUEÑO" DE TODO)
# -----------------------------------------------------------------
class SuscripcionCliente(models.Model):
    nombre_empresa = models.CharField(max_length=255)
    PLAN_EMPRENDEDOR = 'plan_emprendedor'
    PLAN_PRO = 'plan_pro'
    PLAN_EMPRESARIAL = 'plan_empresarial'
    PLAN_CHOICES = [
        (PLAN_EMPRENDEDOR, 'Emprendedor'),
        (PLAN_PRO, 'Profesional'),
        (PLAN_EMPRESARIAL, 'Empresarial'),
    ]
    plan_actual = models.CharField(max_length=30, choices=PLAN_CHOICES, default=PLAN_EMPRENDEDOR)
    subscription_status = models.CharField(max_length=20, default="trialing")
    ha_completado_onboarding = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.nombre_empresa} - Plan {self.get_plan_actual_display()}"


# -----------------------------------------------------------------
# MODELO 2: EL USUARIO/EMPLEADO
# -----------------------------------------------------------------
class User(AbstractUser):
    suscripcion = models.ForeignKey(
        SuscripcionCliente, 
        on_delete=models.CASCADE,
        related_name="miembros", 
        null=True,
        blank=True
    )
    
    # --- ¡¡AQUÍ ESTÁ LA SOLUCIÓN AL ERROR 'clashes'!! ---
    # Sobrescribimos los campos 'groups' y 'user_permissions'
    # para darles un 'related_name' único y evitar el conflicto.
    
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        # Usamos un related_name único
        related_name="inventario_user_groups",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        # Usamos un related_name único
        related_name="inventario_user_permissions",
        related_query_name="user",
    )
    # --- FIN DE LA SOLUCIÓN ---


# ---------- Helper global (máx 1 decimal) ----------
def fmt1(value) -> str:
    # (El resto del archivo es idéntico al anterior)
    try:
        d = Decimal(value or 0)
    except Exception:
        return str(value)
    q = d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{int(q)}" if q == q.to_integral() else f"{q.normalize():f}"

# =========================
#  Unidades (Modelo Global)
# =========================
class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=50, unique=True) 
    def __str__(self):
        return self.nombre

# =========================
#  Materias Primas (Por Empresa)
# =========================
class MateriaPrima(models.Model):
    suscripcion = models.ForeignKey(SuscripcionCliente, on_delete=models.CASCADE, related_name="materias_primas")
    nombre = models.CharField(max_length=120) 
    unidad = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT) 
    stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=3, default=0) 
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["nombre"] 
        unique_together = ("suscripcion", "nombre")
    def __str__(self):
        return self.nombre
    def _fmt_decimal_short(self, x: Decimal, max_dec: int = 1) -> str:
        d = Decimal(x or 0); q = d.quantize(Decimal(10) ** -max_dec, rounding=ROUND_HALF_UP); return f"{int(q)}" if q == q.to_integral() else f"{q.normalize():f}"
    def format_qty(self, qty: Decimal) -> str:
        d = Decimal(qty or 0); u = (self.unidad.nombre or "").lower()
        if u == "kg":
            if d >= 1: return f"{self._fmt_decimal_short(d)} kg"
            g = (d * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP); return f"{int(g)} g"
        if u in ("l", "lt", "litro", "litros"):
            if d >= 1: return f"{self._fmt_decimal_short(d)} l"
            ml = (d * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP); return f"{int(ml)} ml"
        return f"{self._fmt_decimal_short(d)} {self.unidad.nombre}"
    @property
    def stock_fmt(self) -> str: return fmt1(self.stock)
    @property
    def stock_minimo_fmt(self) -> str: return fmt1(self.stock_minimo)

# =========================
#  Kardex (Por Materia Prima)
# =========================
class MovimientoMP(models.Model):
    INGRESO = "INGRESO"; CONSUMO = "CONSUMO"; AJUSTE_POS = "AJUSTE_POS"; AJUSTE_NEG = "AJUSTE_NEG"; MERMA = "MERMA"
    TIPOS = [(INGRESO, "Ingreso"), (CONSUMO, "Consumo"), (AJUSTE_POS, "Ajuste (+)"), (AJUSTE_NEG, "Ajuste (-)"), (MERMA, "Merma")]
    mp = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=12, choices=TIPOS)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    fecha = models.DateTimeField(default=timezone.now)
    nota = models.CharField(max_length=250, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    class Meta: ordering = ["-fecha"] 
    def __str__(self): return f"{self.mp} · {self.tipo} · {fmt1(self.cantidad)}"
    @property
    def cantidad_signed(self) -> Decimal: return self.cantidad if self.tipo in [self.INGRESO, self.AJUSTE_POS] else -self.cantidad
    def save(self, *args, **kwargs):
        with transaction.atomic():
            delta = Decimal("0")
            if self.pk: delta = self.cantidad_signed - MovimientoMP.objects.select_for_update().get(pk=self.pk).cantidad_signed
            else: delta = self.cantidad_signed
            super().save(*args, **kwargs) 
            mp = MateriaPrima.objects.select_for_update().get(pk=self.mp_id)
            mp.stock = (mp.stock or Decimal("0")) + (delta or Decimal("0"))
            mp.save(update_fields=["stock"]) 
    def delete(self, *args, **kwargs):
        with transaction.atomic():
            mp = MateriaPrima.objects.select_for_update().get(pk=self.mp_id)
            mp.stock = (mp.stock or Decimal("0")) - (self.cantidad_signed or Decimal("0"))
            mp.save(update_fields=["stock"])
            super().delete(*args, **kwargs)

# =========================
#  Productos (Por Empresa)
# =========================
class Producto(models.Model):
    suscripcion = models.ForeignKey(SuscripcionCliente, on_delete=models.CASCADE, related_name="productos")
    nombre = models.CharField(max_length=120) 
    unidad = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT) 
    vida_util_dias = models.PositiveIntegerField(default=3) 
    activo = models.BooleanField(default=True)
    class Meta:
        ordering = ["nombre"]
        unique_together = ("suscripcion", "nombre")
    def __str__(self): return self.nombre
    def _fmt_decimal_short(self, x: Decimal, max_dec: int = 1) -> str:
        d = Decimal(x or 0); q = d.quantize(Decimal(10) ** -max_dec, rounding=ROUND_HALF_UP); return f"{int(q)}" if q == q.to_integral() else f"{q.normalize():f}"
    def format_qty(self, qty: Decimal) -> str:
        u = (self.unidad.nombre or "").lower(); d = Decimal(qty or 0)
        if u == "kg":
            if d >= 1: return f"{self._fmt_decimal_short(d)} kg"
            g = (d * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP); return f"{int(g)} g"
        if u in ("l", "lt", "litro", "litros"):
            if d >= 1: return f"{self._fmt_decimal_short(d)} l"
            ml = (d * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP); return f"{int(ml)} ml"
        return f"{self._fmt_decimal_short(d)} {self.unidad.nombre}"

# =========================
#  Recetas (Por Producto)
# =========================
class Receta(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="recetas")
    nombre = models.CharField(max_length=120, default="Tradicional")
    version = models.PositiveIntegerField(default=1)
    rendimiento_por_lote = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    descripcion = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    activo = models.BooleanField(default=True)
    class Meta:
        unique_together = ("producto", "nombre", "version")
        ordering = ["producto__nombre", "-version"] 
    def __str__(self): return f"{self.producto.nombre} - {self.nombre} v{self.version}"

class RecetaLinea(models.Model):
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name="lineas")
    mp = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT) 
    cantidad = models.DecimalField(max_digits=12, decimal_places=3) 
    class Meta:
        unique_together = ("receta", "mp")
        ordering = ["mp__nombre"]
    def __str__(self): return f"{self.receta} → {self.mp} x {fmt1(self.cantidad)}"
    def por_lote_fmt(self) -> str: return self.mp.format_qty(self.cantidad)
    def total_para(self, lotes) -> Decimal: return Decimal(self.cantidad) * Decimal(lotes)
    def total_para_fmt(self, lotes) -> str: return self.mp.format_qty(self.total_para(lotes))

# =========================
#  Producción / Lotes
# =========================
class OrdenProduccion(models.Model):
    BORRADOR = "BORRADOR"; CONSUMIDA = "CONSUMIDA"; ESTADOS = [(BORRADOR, "Borrador"), (CONSUMIDA, "Consumida")]
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    receta = models.ForeignKey(Receta, on_delete=models.PROTECT)
    lotes = models.DecimalField(max_digits=12, decimal_places=3, default=1) 
    fecha = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=BORRADOR)
    nota = models.CharField(max_length=250, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    class Meta: ordering = ["-fecha"]
    def __str__(self): return f"OP #{self.id or '—'} · {self.producto} · {fmt1(self.lotes)} lote(s)"
    @property
    def unidades_totales(self): return (self.receta.rendimiento_por_lote or Decimal("0")) * (self.lotes or Decimal("0"))
    @property
    def unidades_totales_fmt(self) -> str: return self.producto.format_qty(self.unidades_totales)
    @property
    def detalle_consumo(self):
        rows = [];
        for ln in self.receta.lineas.select_related("mp"):
            total = Decimal(ln.cantidad) * Decimal(self.lotes or 0)
            rows.append({"mp": ln.mp, "por_lote": ln.por_lote_fmt(), "total_fmt": ln.mp.format_qty(total)})
        return rows
    def validar_stock(self):
        faltantes = []
        for ln in self.receta.lineas.select_related("mp"):
            requerido = Decimal(ln.cantidad) * Decimal(self.lotes)
            if ln.mp.suscripcion_id != self.producto.suscripcion_id:
                raise ValidationError(f"Error de datos: La MP {ln.mp} y el Producto {self.producto} son de empresas distintas.")
            if (ln.mp.stock or Decimal("0")) < requerido:
                faltantes.append(f"{ln.mp.nombre}: req {fmt1(requerido)} / stock {fmt1(ln.mp.stock or 0)}")
        if faltantes: raise ValidationError("Stock insuficiente de MP → " + "; ".join(faltantes))
    def consumir_mp(self, user=None):
        for ln in self.receta.lineas.select_related("mp"):
            MovimientoMP.objects.create(mp=ln.mp, tipo=MovimientoMP.CONSUMO, cantidad=Decimal(ln.cantidad) * Decimal(self.lotes), nota=f"OP {self.pk} · {self.producto}", created_by=user)
    def ejecutar(self, user=None):
        if self.estado == self.CONSUMIDA: return 
        self.validar_stock() 
        with transaction.atomic():
            self.consumir_mp(user=user); self.estado = self.CONSUMIDA; self.save(update_fields=["estado"])
            unidades = self.unidades_totales; fecha_prod = self.fecha
            venc = (fecha_prod + timedelta(days=self.producto.vida_util_dias)).date()
            codigo = LoteProducto.generar_codigo(self.producto, fecha_prod)
            LoteProducto.objects.create(producto=self.producto, codigo=codigo, op=self, fecha_produccion=fecha_prod, fecha_vencimiento=venc, cantidad_inicial=unidades, cantidad_disponible=unidades, created_by=user)

class LoteProducto(models.Model):
    OK = "OK"; POR_RALLAR = "RALLAR"; VENCIDO = "VENCIDO"
    ESTADOS = [(OK, "OK"), (POR_RALLAR, "Por pan rallado"), (VENCIDO, "Vencido")]
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="lotes")
    codigo = models.CharField(max_length=30, unique=True) 
    op = models.ForeignKey(OrdenProduccion, null=True, blank=True, on_delete=models.SET_NULL, related_name="lotes_creados")
    fecha_produccion = models.DateTimeField(default=timezone.now)
    fecha_vencimiento = models.DateField()
    cantidad_inicial = models.DecimalField(max_digits=12, decimal_places=3)
    cantidad_disponible = models.DecimalField(max_digits=12, decimal_places=3)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=OK)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["fecha_vencimiento", "-cantidad_disponible"]
    def __str__(self): return f"{self.codigo} · {self.producto}"
    @property
    def cantidad_inicial_fmt(self) -> str: return self.producto.format_qty(self.cantidad_inicial)
    @property
    def cantidad_disponible_fmt(self) -> str: return self.producto.format_qty(self.cantidad_disponible)
    @staticmethod
    def generar_codigo(producto, fecha_dt):
        base = f"{producto.id}-{fecha_dt.strftime('%Y%m%d')}"
        n = LoteProducto.objects.filter(producto__suscripcion=producto.suscripcion, producto=producto, fecha_produccion__date=fecha_dt.date()).count() + 1
        return f"{base}-{n:03d}" 
    @property
    def dias_restantes(self): return (self.fecha_vencimiento - timezone.localdate()).days
    def _calcular_estado(self):
        d = self.dias_restantes
        if d < 0: return self.VENCIDO
        elif d <= 1: return self.POR_RALLAR
        return self.OK
    def save(self, *args, **kwargs):
        self.estado = self._calcular_estado()
        super().save(*args, **kwargs)

# =========================
#  Ventas (Por Empresa)
# =========================
class Venta(models.Model):
    BORRADOR = "BORRADOR"; CONFIRMADA = "CONFIRMADA"; ESTADOS = [(BORRADOR, "Borrador"), (CONFIRMADA, "Confirmada")]
    suscripcion = models.ForeignKey(SuscripcionCliente, on_delete=models.CASCADE, related_name="ventas")
    fecha = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=BORRADOR)
    nota = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    class Meta: ordering = ["-fecha"]
    def __str__(self): return f"Venta #{self.id or '—'}"
    def validar_stock(self):
        if self.lineas.count() == 0: raise ValidationError("La venta no tiene líneas.")
        faltantes = []
        for ln in self.lineas.select_related("producto"):
            if ln.producto.suscripcion_id != self.suscripcion_id:
                raise ValidationError(f"Error de datos: El Producto {ln.producto} es de una empresa distinta a esta Venta.")
            qs = LoteProducto.objects.filter(producto=ln.producto, estado__in=[LoteProducto.OK, LoteProducto.POR_RALLAR], cantidad_disponible__gt=0).order_by("fecha_vencimiento", "created_at")
            disp = sum((l.cantidad_disponible or Decimal("0")) for l in qs)
            if disp < ln.cantidad:
                faltantes.append(f"{ln.producto}: req {fmt1(ln.cantidad)} / disp {fmt1(disp)}")
        if faltantes: raise ValidationError("Stock insuficiente → " + "; ".join(faltantes))
    @transaction.atomic 
    def consumir_fifo(self, user=None):
        if self.estado == self.CONFIRMADA: return 
        self.validar_stock() 
        for ln in self.lineas.select_related("producto"):
            pendiente = Decimal(ln.cantidad) 
            lotes = LoteProducto.objects.select_for_update().filter(producto=ln.producto, estado__in=[LoteProducto.OK, LoteProducto.POR_RALLAR], cantidad_disponible__gt=0).order_by("fecha_vencimiento", "created_at")
            for lote in lotes:
                if pendiente <= 0: break 
                tomar = min(pendiente, lote.cantidad_disponible)
                if tomar > 0:
                    lote.cantidad_disponible = (lote.cantidad_disponible or Decimal("0")) - tomar; lote.save()
                    VentaConsumo.objects.create(venta=self, linea=ln, lote=lote, cantidad=tomar, created_by=user)
                    pendiente -= tomar
            if pendiente > 0: raise ValidationError(f"Stock insuficiente durante consumo: {ln.producto}")
        self.estado = self.CONFIRMADA; self.save(update_fields=["estado"])

class VentaLinea(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="lineas")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3) 
    def __str__(self): return f"{self.producto} x {fmt1(self.cantidad)}"
    @property
    def cantidad_fmt(self) -> str: return self.producto.format_qty(self.cantidad)

class VentaConsumo(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="consumos")
    linea = models.ForeignKey(VentaLinea, on_delete=models.CASCADE, related_name="consumos")
    lote = models.ForeignKey(LoteProducto, on_delete=models.PROTECT, related_name="consumos")
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    class Meta: ordering = ["created_at"]
    def __str__(self): return f"{self.venta_id} · {self.lote.codigo} · {fmt1(self.cantidad)}"
    @property
    def cantidad_fmt(self) -> str: return self.lote.producto.format_qty(self.cantidad)

# =========================
#  Históricos (Por Empresa)
# =========================
class HistoricoVenta(models.Model):
    suscripcion = models.ForeignKey(SuscripcionCliente, on_delete=models.CASCADE, related_name="historico_ventas")
    fecha = models.DateField()
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    class Meta: ordering = ["fecha"]
    def __str__(self): return f"{self.fecha} · {self.producto} · {self.cantidad}"