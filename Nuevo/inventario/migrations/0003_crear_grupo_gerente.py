# inventario/migrations/0003_crear_grupo_gerente.py

from django.db import migrations

def crear_grupo_gerente(apps, schema_editor):
    """
    Crea el grupo "Gerente" y le asigna todos los permisos
    de la aplicación "inventario".
    """
    # Obtenemos los modelos necesarios en el contexto de la migración
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # 1. Crear el grupo "Gerente" (o obtenerlo si ya existe)
    gerente_group, created = Group.objects.get_or_create(name='Gerente')

    # 2. Encontrar todos los permisos de la app 'inventario'
    #    Buscamos todos los modelos de nuestra app
    app_content_types = ContentType.objects.filter(app_label='inventario')

    #    Buscamos todos los permisos asociados a esos modelos
    app_permissions = Permission.objects.filter(
        content_type__in=app_content_types
    )

    # 3. Asignar todos esos permisos al grupo "Gerente"
    gerente_group.permissions.set(app_permissions)
    if created:
        print("Grupo 'Gerente' creado y permisos asignados.")

def revertir_carga(apps, schema_editor):
    """
    Borra el grupo si deshacemos la migración.
    """
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Gerente').delete()

class Migration(migrations.Migration):

    dependencies = [
        # Depende de la migración anterior (la de precargar unidades)
        ('inventario', '0002_precargar_unidades'),
    ]

    operations = [
        # Le decimos a Django que ejecute nuestra función
        migrations.RunPython(crear_grupo_gerente, revertir_carga),
    ]