# inventario/migrations/0002_precargar_unidades.py
from django.db import migrations

UNIDADES_ESTANDAR = ['kg', 'g', 'lt', 'ml', 'unidad', 'cc']

def cargar_unidades_iniciales(apps, schema_editor):
    UnidadMedida = apps.get_model('inventario', 'UnidadMedida')
    for nombre_unidad in UNIDADES_ESTANDAR:
        UnidadMedida.objects.get_or_create(nombre=nombre_unidad)

def revertir_carga(apps, schema_editor):
    UnidadMedida = apps.get_model('inventario', 'UnidadMedida')
    UnidadMedida.objects.filter(nombre__in=UNIDADES_ESTANDAR).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('inventario', '0001_initial'), # Asegúrate que '0001_initial' sea tu primera migración
    ]
    operations = [
        migrations.RunPython(cargar_unidades_iniciales, revertir_carga),
    ]