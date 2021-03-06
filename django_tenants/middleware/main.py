from django.conf import settings
from django.db import connection
from django.http import Http404, HttpResponse
from django.urls import set_urlconf
from django.utils.deprecation import MiddlewareMixin

from django_tenants.utils import remove_www, get_public_schema_name, get_tenant_domain_model, get_tenant_model


class TenantMainMiddleware(MiddlewareMixin):
    TENANT_NOT_FOUND_EXCEPTION = Http404
    """
    This middleware should be placed at the very top of the middleware stack.
    Selects the proper database schema using the request host. Can fail in
    various ways which is better than corrupting or revealing data.
    """

    @staticmethod
    def hostname_from_request(request):
        """ Extracts hostname from request. Used for custom requests filtering.
            By default removes the request's port and common prefixes.
        """
        return remove_www(request.get_host().split(':')[0])

    def get_tenant(self, domain_model, hostname):
        domain = domain_model.objects.select_related(
            'tenant').get(domain=hostname)
        return domain.tenant

    def process_request(self, request):
        # Connection needs first to be at the public schema, as this is where
        # the tenant metadata is stored.
        connection.set_schema_to_public()
        hostname = self.hostname_from_request(request)
        print('IN PROCESS REQUEST - METHOD = ', request.method)
        print('IN PROCESS REQUEST - META = ', request.META)
        print('IN PROCESS REQUEST - HEADERS = ', request.headers)

        tenant_id = request.headers.get('x-tenant-id')
        print('X TENTANT = ', tenant_id)

        domain_model = get_tenant_domain_model()

        if request.method != 'OPTIONS' and request.method != 'GET':
            try:
                tenant_id = request.headers.get('X-TENANT-ID')
                print('TENANT ID = ', tenant_id)
                tenant_model = get_tenant_model()
                if tenant_model.objects.filter(tenant_id=tenant_id).exists():
                    tenant = tenant_model.objects.get(tenant_id=tenant_id)
                    print('TENANT = ', tenant.__dict__)
                    tenant.domain_url = hostname
                    request.tenant = tenant

                    connection.set_tenant(request.tenant)
                else:
                    print('NO TENANT')
                    return HttpResponse('Unauthorized - Invalid Tenant Id', status=401)
            except domain_model.DoesNotExist:
                raise self.TENANT_NOT_FOUND_EXCEPTION(
                    'No tenant for id "%s"' % tenant_id)

        # if request.method != 'OPTIONS':
        #     try:
        #         tenant_id = request.headers.get('X-TENANT-ID')
        #         print('TENANT ID = ', tenant_id)
        #         tenant_model = get_tenant_model()
        #         tenant = tenant_model.objects.get(tenant_id=tenant_id)
        #         print('TENANT = ', tenant.__dict__)
        #     except domain_model.DoesNotExist:
        #         raise self.TENANT_NOT_FOUND_EXCEPTION(
        #             'No tenant for id "%s"' % tenant_id)

        #     tenant.domain_url = hostname
        #     request.tenant = tenant

        #     connection.set_tenant(request.tenant)

        # ** OLD DOMAIN METHOD***
        # try:
        #     tenant = self.get_tenant(domain_model, hostname)
        #     print('TENANT = ', tenant)
        # except domain_model.DoesNotExist:
        #     raise self.TENANT_NOT_FOUND_EXCEPTION('No tenant for hostname "%s"' % hostname)

        # tenant.domain_url = hostname
        # request.tenant = tenant

        # connection.set_tenant(request.tenant)
        # ***************

        # Do we have a public-specific urlconf?
        if hasattr(settings, 'PUBLIC_SCHEMA_URLCONF') and request.tenant.schema_name == get_public_schema_name():
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
            set_urlconf(request.urlconf)
