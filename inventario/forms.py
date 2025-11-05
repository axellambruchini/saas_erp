# inventario/forms.py
# ============================================================
#  IMPORTACIONES
# ============================================================
from decimal import Decimal, ROUND_HALF_UP
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User 

from .models import (
    MateriaPrima, MovimientoMP,
    OrdenProduccion, Receta, RecetaLinea, Producto,
    Venta, VentaLinea,
    SuscripcionCliente
)

# ============================================================
#  FORMULARIOS DE USUARIO
# ============================================================

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",) 

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


# ============ Utilidad numérica amigable ============

NUM_WIDGET = forms.NumberInput(attrs={"step": "0.1", "inputmode": "decimal"})

class SmartDecimalField(forms.DecimalField):
    """
    Campo personalizado que fuerza 1 decimal por defecto
    y redondea cualquier entrada a 1 decimal.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('decimal_places', 1) 
        kwargs.setdefault('max_digits', 12)
        kwargs.setdefault('widget', NUM_WIDGET)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(" ", "").replace(",", ".")
        val = super().to_python(value)
        if val is None:
            return None
        rounding_decimal = Decimal(10) ** -self.decimal_places
        return val.quantize(rounding_decimal, rounding=ROUND_HALF_UP)

    def prepare_value(self, value):
        try: d = Decimal(str(value))
        except Exception: return value
        rounding_decimal = Decimal(10) ** -self.decimal_places
        q = d.quantize(rounding_decimal, rounding=ROUND_HALF_UP)
        return str(int(q)) if q == q.to_integral() else f"{q.normalize():f}"


# =========================
#  Materias Primas / Movimientos
# =========================

class MateriaPrimaForm(forms.ModelForm):
    stock_minimo = SmartDecimalField(min_value=Decimal("0"), required=False) # min_value=0 está bien
    class Meta:
        model = MateriaPrima
        fields = ("nombre", "unidad", "stock_minimo", "activo")
    def save(self, commit=True, user=None):
        instancia = super().save(commit=False)
        if user and user.suscripcion:
            instancia.suscripcion = user.suscripcion
        if commit:
            instancia.save()
        return instancia


class MovimientoIngresoForm(forms.ModelForm):
    # «-- ¡CAMBIO AQUÍ! --»
    cantidad = SmartDecimalField(min_value=Decimal("0.1")) # Cambiado de 0.001 a 0.1
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        if user and user.suscripcion:
            self.fields['mp'].queryset = MateriaPrima.objects.filter(suscripcion=user.suscripcion, activo=True)
    class Meta:
        model = MovimientoMP
        fields = ["mp", "cantidad", "nota"] 
    def save(self, user=None, commit=True):
        obj = super().save(commit=False); obj.tipo = MovimientoMP.INGRESO
        if user: obj.created_by = user
        if commit: obj.save()
        return obj


class MovimientoAjusteForm(forms.ModelForm):
    TIPO = forms.ChoiceField(choices=[(MovimientoMP.AJUSTE_POS, "Ajuste (+)"), (MovimientoMP.AJUSTE_NEG, "Ajuste (-)")])
    # «-- ¡CAMBIO AQUÍ! --»
    cantidad = SmartDecimalField(min_value=Decimal("0.1")) # Cambiado de 0.001 a 0.1
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        if user and user.suscripcion:
            self.fields['mp'].queryset = MateriaPrima.objects.filter(suscripcion=user.suscripcion, activo=True)
    class Meta:
        model = MovimientoMP
        fields = ["mp", "cantidad", "nota"]
    def save(self, user=None, commit=True):
        obj = super().save(commit=False); obj.tipo = self.cleaned_data["TIPO"]
        if user: obj.created_by = user
        if commit: obj.save()
        return obj

class MovimientoMermaForm(forms.ModelForm):
    # «-- ¡CAMBIO AQUÍ! --»
    cantidad = SmartDecimalField(min_value=Decimal("0.1")) # Cambiado de 0.001 a 0.1
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        if user and user.suscripcion:
            self.fields['mp'].queryset = MateriaPrima.objects.filter(suscripcion=user.suscripcion, activo=True)
    class Meta:
        model = MovimientoMP
        fields = ["mp", "cantidad", "nota"]
    def save(self, user=None, commit=True):
        obj = super().save(commit=False); obj.tipo = MovimientoMP.MERMA
        if user: obj.created_by = user
        if commit: obj.save()
        return obj

# =========================
#  Recetas
# =========================
class RecetaForm(forms.ModelForm):
    nombre = forms.CharField(label="Nombre de la receta", widget=forms.TextInput(attrs={"placeholder": "Ej: Tradicional, Integral, Completos …"}))
    # «-- ¡CAMBIO AQUÍ! --»
    rendimiento_por_lote = SmartDecimalField(
        min_value=Decimal("0.1"), # Cambiado de 0.001 a 0.1
        label="Rendimiento por lote (en unidad del producto)"
    )
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        if user and user.suscripcion:
            self.fields['producto'].queryset = Producto.objects.filter(suscripcion=user.suscripcion, activo=True)
    class Meta:
        model = Receta
        fields = ["producto", "nombre", "version", "rendimiento_por_lote", "activo"]

class RecetaLineaForm(forms.ModelForm):
    # (Este lo dejamos con 3 decimales a propósito,
    #  para la conversión de gramos a kg)
    cantidad_valor = SmartDecimalField(
        min_value=Decimal("0.001"),
        decimal_places=3, 
        widget=forms.NumberInput(attrs={"step": "1", "inputmode": "decimal"}),
        label="Cantidad"
    )
    cantidad_unidad = forms.ChoiceField(choices=[("auto", "—")], label="Unidad")
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        if user and user.suscripcion:
            self.fields['mp'].queryset = MateriaPrima.objects.filter(suscripcion=user.suscripcion, activo=True)
    class Meta:
        model = RecetaLinea
        fields = ["mp"] 
    def clean(self):
        c = super().clean(); mp = c.get("mp"); val = c.get("cantidad_valor"); uin = c.get("cantidad_unidad") 
        if not mp or not val: return c
        unidad_base = (mp.unidad.nombre or "").lower(); cantidad_base = Decimal(val) 
        if unidad_base == "kg":
            if uin and uin.lower() == "g": cantidad_base = Decimal(val) / Decimal("1000")
        elif unidad_base in ("l", "lt", "litro", "litros"):
            if uin and uin.lower() == "ml": cantidad_base = Decimal(val) / Decimal("1000")
        self.cleaned_data["cantidad_base"] = cantidad_base
        return c
    def save(self, commit=True):
        inst = super().save(commit=False); inst.cantidad = self.cleaned_data.get("cantidad_base") or Decimal("0")
        if commit: inst.save()
        return inst

class RecetaLineaBaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean(); mps = set(); at_least_one = False
        for form in self.forms: 
            if not getattr(form, "cleaned_data", None): continue
            if form.cleaned_data.get("DELETE"): continue
            mp = form.cleaned_data.get("mp")
            if mp:
                at_least_one = True
                if mp in mps: form.add_error("mp", "La materia prima está duplicada.")
                mps.add(mp)
        if not at_least_one:
            raise forms.ValidationError("La receta debe tener al menos un ingrediente.")

RecetaLineaFormSet = inlineformset_factory(Receta, RecetaLinea, form=RecetaLineaForm, formset=RecetaLineaBaseFormSet, extra=1, can_delete=True)

# =========================
#  Producción (OP)
# =========================
class OrdenProduccionForm(forms.ModelForm):
    confirmar_y_ejecutar = forms.BooleanField(required=False, label="Confirmar y ejecutar (descontar MP y generar lote)")
    # «-- ¡CAMBIO AQUÍ! --»
    lotes = SmartDecimalField(label="Cantidad a producir", min_value=Decimal("0.1")) # Cambiado de 0.001 a 0.1
    class Meta:
        model = OrdenProduccion
        fields = ["producto", "receta", "lotes", "nota", "confirmar_y_ejecutar"]
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None); super().__init__(*args, **kwargs)
        if user and user.suscripcion:
            self.fields['producto'].queryset = Producto.objects.filter(suscripcion=user.suscripcion, activo=True)
        prod = None
        if self.data.get("producto"): 
            try:
                prod_id = int(self.data.get("producto"))
                prod = Producto.objects.get(pk=prod_id, suscripcion=user.suscripcion)
            except (Producto.DoesNotExist, TypeError, ValueError): prod = None
        elif self.instance and self.instance.pk: prod = self.instance.producto
        if prod:
            self.fields["receta"].queryset = Receta.objects.filter(producto=prod, activo=True)
            self.fields["lotes"].label = f"Cantidad a producir ({prod.unidad.nombre})"
        else:
            self.fields["receta"].queryset = Receta.objects.none()
    def clean(self):
        c = super().clean(); prod = c.get("producto"); rec = c.get("receta"); lotes = c.get("lotes")
        if rec and prod and rec.producto_id != prod.id:
            raise forms.ValidationError("La receta seleccionada no corresponde a ese producto.")
        if lotes and lotes <= 0: self.add_error("lotes", "La cantidad a producir debe ser > 0.")
        if c.get("confirmar_y_ejecutar") and rec and lotes:
            faltantes = []
            for ln in rec.lineas.select_related("mp"):
                req = (ln.cantidad or Decimal("0")) * lotes; disp = ln.mp.stock or Decimal("0")
                if disp < req:
                    faltantes.append(f"{ln.mp.nombre}: req {req} / stock {disp}")
            if faltantes: raise forms.ValidationError("Stock insuficiente de MP → " + "; ".join(faltantes))
        return c

# =========================
#  Ventas
# =========================
class VentaForm(forms.ModelForm):
    confirmar_y_consumir = forms.BooleanField(required=False, label="Confirmar venta y consumir lotes (FEFO)")
    class Meta:
        model = Venta
        fields = ["nota", "confirmar_y_consumir"]
    def save(self, commit=True, user=None):
        instancia = super().save(commit=False)
        if user and user.suscripcion:
            instancia.suscripcion = user.suscripcion
        if commit: instancia.save()
        return instancia

class VentaLineaForm(forms.ModelForm):
    # «-- ¡CAMBIO AQUÍ! --»
    cantidad = SmartDecimalField(min_value=Decimal("0.1")) # Cambiado de 0.001 a 0.1
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        if user and user.suscripcion:
            self.fields['producto'].queryset = Producto.objects.filter(suscripcion=user.suscripcion, activo=True)
    class Meta:
        model = VentaLinea
        fields = ("producto", "cantidad")

class VentaLineaBaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean(); at_least_one = False; productos = {} 
        for form in self.forms:
            if not getattr(form, "cleaned_data", None): continue
            if form.cleaned_data.get("DELETE"): continue
            prod = form.cleaned_data.get("producto"); qty = form.cleaned_data.get("cantidad")
            if not prod and not qty: continue
            at_least_one = True
            if qty and qty <= 0: form.add_error("cantidad", "La cantidad debe ser > 0.")
            if prod in productos: form.add_error("producto", "Producto repetido en otra línea. Combínalas.")
            productos[prod] = True
        if not at_least_one:
            raise forms.ValidationError("La venta debe tener al menos una línea.")

VentaLineaFormSet = inlineformset_factory(Venta, VentaLinea, form=VentaLineaForm, formset=VentaLineaBaseFormSet, extra=2, can_delete=True)

# =========================
#  Formularios de Carga de Archivos
# =========================
class UploadFileForm(forms.Form):
    file = forms.FileField(label="Archivo CSV/Excel", help_text="Sube un archivo con columnas 'fecha' y 'valor'")

class UploadInvoiceForm(forms.Form):
    invoice_file = forms.FileField(label="Subir factura (imagen o PDF)", widget=forms.ClearableFileInput(attrs={'class': '...'}))