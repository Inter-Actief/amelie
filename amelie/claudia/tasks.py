from celery.task import task


@task
def verify_instance(obj_type, ident):
    from amelie.claudia.models import Mapping
    from amelie.claudia.clau import Claudia

    obj = Mapping.get_object_from_mapping(obj_type, ident)
    Claudia().do_verify(obj)


@task
def verify_mapping(cid):
    from amelie.claudia.models import Mapping
    from amelie.claudia.clau import Claudia

    mapping = Mapping.objects.get(id=cid)
    Claudia().do_verify(mapping)
