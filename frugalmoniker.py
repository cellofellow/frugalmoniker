import copy
import re
from datetime import datetime

import requests
import xmltodict


class ContactValidationError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class NamecheapClient(object):
    '''
    A client of the NameCheap.com API. Handles commonly run commands on the
    API. It uses the requests library and xmltodict.

    To initialize a connection create an instance of this class with the
    API username, API key, NameCheap.com username, and your current IP. You can
    then call methods on the client object to interact with NameCheap.com.

    ClientIP option will automatically grab your IP from the web if you don't
    provide it. UserName is set to ApiUser if not provided.
    '''
    def __init__(self, api_user, api_key, username=None, client_ip=None,
                 environment='https://api.namecheap.com/xml.response'):
        if not client_ip:
            client_ip = requests.get('http://icanhazip.com').text.strip()
        username = api_user if not username else username

        self.base_opts = {
            'ApiUser': api_user,
            'ApiKey': api_key,
            'UserName': username,
            'ClientIp': client_ip,
        }
        self.base_url = environment

    def request(self, **kwargs):
        '''
        General purpose API call function. Sends an HTTP POST request with all
        the required Global Parameters (http://goo.gl/gvGfu) to at get started
        on a request. All keyword arguments passed in are added to the request.

        Returns a requests response object.

        Example usage:

        >>> response = client.request(command='namecheap.domains.getList')
        '''

        opts = copy.copy(self.base_opts)
        opts.update(kwargs)
        return requests.post(self.base_url, data=opts)

    def domains_create(self, domain_name, **kwargs):
        '''
        Send a request with the command 'namecheap.domains.create'.
        Requires a domain_name to register, and at least a Contact registrant,
        with optional admin, tech, and aux_billing Contacts. If the admin,
        tech, or aux_billing Contacts aren't provided, they will be copied from
        the registrant Contact.

        Also optionally a Years option can be supplied to say how long to
        register the domain for. Defaults to 1 year.

        See http://goo.gl/Z4UIN for docs on the namecheap.domains.create
        command.

        Example usage:

        >>> registrant = Contact(first_name='John', last_name='Doe'...)
        >>> response = client.domains_create('example.com',
                                             registrant=registrant)
        '''

        command = 'namecheap.domains.create'
        years = kwargs.get('years', 1)
        registrant = kwargs['registrant']
        registrant._prefix = 'Registrant'

        if kwargs.get('admin'):
            admin = kwargs.get('admin')
        else:
            admin = copy.copy(registrant)
            admin._prefix = 'Admin'
        if kwargs.get('tech'):
            tech = kwargs.get('tech')
        else:
            tech = copy.copy(registrant)
            tech._prefix = 'Tech'
        if kwargs.get('aux_billing'):
            aux_billing = kwargs.get('aux_billing')
        else:
            aux_billing = copy.copy(registrant)
            aux_billing._prefix = 'AuxBilling'

        get_opts = {'Command': command, 'DomainName': domain_name,
                    'Years': years}
        get_opts.update(registrant.as_dict())
        get_opts.update(admin.as_dict())
        get_opts.update(tech.as_dict())
        get_opts.update(aux_billing.as_dict())

        response = self.request(**get_opts)

        # TODO Actually process the response with xmltodict.
        return response

    def common_get_list(self, command, list_type='all', sort_by='name',
                        page_size=10, page=1, search_term=None):
        LIST_TYPES = {
            'all': 'ALL',
            'expiring': 'EXPIRING',
            'expired': 'EXPIRED',
        }
        SORT_TYPES = {
            'name': 'NAME',
            '-name': 'NAME_DESC',
            'expire_date': 'EXPIREDATE',
            '-expire_date': 'EXPIREDATE_DESC',
            'create_date': 'CREATEDATE',
            '-create_date': 'CREATEDATE_DESC',
        }

        try:
            list_type = LIST_TYPES[list_type]
        except KeyError:
            raise ValueError('Invalid list_type.')
        try:
            sort_by = SORT_TYPES[sort_by]
        except KeyError:
            raise ValueError('Invalid sort_by')

        get_opts = {'Command': command, 'ListType': list_type,
                    'SortBy': sort_by, 'Page': page, 'PageSize': page_size}
        if search_term:
            get_opts['SearchTerm'] = search_term

        return self.request(**get_opts)

    def domains_get_list(self, **kwargs):
        '''
        Send a request with the command 'namecheap.domains.getList'.
        Fetches a list of registered domains. There are no required arguments.

        Optional arguments:
            list_type:   can be "all", "expiring", or "expired".
            sort_by:     can be "name", "expire_date", or "create_date",
                         and a "-" at the front of each to reverse the sort.
            page_size:   how many to paginate by.
            page:        which page to get
            search_term: keyword to search by

        See http://goo.gl/v7Toh for docs on the namecheap.domains.getList
        command.

        Example usage:

        >>> response = client.domains_get_list(sort_by='create_date')
        '''
        command = 'namecheap.domains.getList'
        response = self.common_get_list(command, **kwargs)

        doc = xmltodict.parse(response.text)
        errors = doc['ApiResponse']['Errors']
        if errors:
            raise Exception(errors)

        result = doc['ApiResponse']['CommandResponse']['DomainGetListResult']
        domains = result['Domain']
        domains = [Domain(self, **{k[1:]: v for k, v in domain.iteritems()})
                   for domain in domains]
        return domains

    def domains_dns_set_custom(self, sld, tld, nameservers):
        '''
        Send a request with the command 'namecheap.domains.dns.setCustom'.
        Sets custom nameservers on a provided domain name.

        Domain name is provided split into second-level domain (sld) and
        top-level domain (tld). Provide nameservers as an iterable of strings.

        The server will check that the provided nameservers exist, and if it
        doesn't it will return errors and this method will raise an exception.

        See http://goo.gl/0x6nh for docs on namecheap.domains.dns.setCustom
        command.

        Example usage:

        >>> response = client.domains_dns_set_custom('example', 'com', [
                'ns1.example.com', 'ns2.example.com'])
        '''
        command = 'namecheap.domains.dns.setCustom'
        get_opts = {'Command': command, 'SLD': sld, 'TLD': tld}
        nameservers = ','.join(ns.upper() for ns in nameservers)
        get_opts['Nameservers'] = nameservers

        response = self.request(**get_opts)

        doc = xmltodict.parse(response.text)
        errors = doc['ApiResponse']['Errors']
        if errors:
            raise Exception(errors)

        # TODO Actually process the response with xmltodict
        return response
    
    def ssl_create(self, ssl_type, years=1):
        command = 'namecheap.ssl.create'
        if not ssl_type in (
            'QuickSSL', 'QuickSSL Premium', 'RapidSSL', 'RapidSSL Wildcard',
            'PremiumSSL', 'InstantSSL', 'PositiveSSL', 'PositiveSSL Wildcard',
            'True BusinessID with EV', 'True BusinessID ',
            'True BusinessID Wildcard ', 'Secure Site ', 'Secure Site Pro ',
            'Secure Site with EV ', 'Secure Site Pro with EV', 'EssentialSSL',
            'EssentialSSL Wildcard', 'InstantSSL Pro', 'Premiumssl wildcard',
            'EV SSL', 'EV SSL SGC', 'SSL123', 'SSL Web Server',
            'SGC Super Certs', 'SSL Webserver EV'):
            raise ValueError('Invalid SSL Certificate Type')

        get_opts = {'Command': command, 'Years': years, 'Type': ssl_type}
        response = self.request(**get_opts)

        # TODO Actually process response with xmltodict
        return response

    def ssl_get_list(self, **kwargs):
        command = 'namecheap.ssl.getList'
        response = self.common_get_list(command, **kwargs)
        return response

        doc = xmltodict.parse(response.text)
        errors = doc['ApiResponse']['Errors']
        if errors:
            raise Exception(errors)

        result = doc['ApiResponse']['CommandResponse']['SSLGetListResult']
        certificates = result['Domain']
        return domains


class Domain(object):
    def __init__(self, client, **kwargs):
        self.client = client
        self._original_dict = kwargs
        self.auto_renew = kwargs.get('AutoRenew')
        created = kwargs.get('Created')
        self.created = datetime.strptime(created, '%m/%d/%Y').date()
        expires = kwargs.get('Expires')
        self.expires = datetime.strptime(expires, '%m/%d/%Y').date()
        self.id = int(kwargs.get('ID'))
        self.is_expired = True if kwargs.get('IsExpired') == 'true' else False
        self.is_locked = True if kwargs.get('IsLocked') == 'true' else False
        self.name = kwargs.get('Name')
        self.user = kwargs.get('User')
        self.whois_guard = kwargs.get('WhoisGuard')

    @property
    def tld(self):
        return self.name.split('.')[1]

    @property
    def sld(self):
        return self.name.split('.')[0]

    def set_nameservers(self, nameservers):
        '''
        Set the nameservers on this domain. Takes a list of nameservers.
        Calls NamecheapClient.domains_dns_set_custom().
        '''
        return self.client.domains_dns_set_custom(
            self.sld, self.tld, nameservers)


class Contact(object):
    __required_fields = (
        'first_name',
        'last_name',
        'address1',
        'city',
        'state_province',
        'country',
        'postal_code',
        'phone',
        'email_address',
    )

    def __init__(self, prefix='', **kwargs):
        self._prefix = prefix
        # Use dict.get() for optional items, use dict[] for required.
        self.organization_name = kwargs.get('organization_name')
        self.job_title = kwargs.get('job_title')
        self.first_name = kwargs['first_name']
        self.last_name = kwargs['last_name']
        self.address1 = kwargs['address1']
        self.address2 = kwargs.get('address2')
        self.city = kwargs['city']
        self.state_province = kwargs['state_province']
        self.state_province_choice = kwargs.get('state_province_choice')
        self.postal_code = kwargs['postal_code']
        self.country = kwargs['country']
        self.phone = kwargs['phone']
        self.phone_ext = kwargs.get('phone_ext')
        self.fax = kwargs.get('fax')
        self.email_address = kwargs.get('email') or kwargs['email_address']

        self.validate()

    def validate(self):
        for field in self.__required_fields:
            if not getattr(self, field):
                raise ContactValidationError('{} is required'.format(field))

        if not self._validate_phone_number(self.phone):
            raise ContactValidationError('phone is not in valid format')
        if self.fax and not self._validate_phone_number(self.fax):
            raise ContactValidationError('fax is not in valid format')

    def _validate_phone_number(self, number):
        phone_regex = re.compile('\+\d{3}\.\d{7}')
        if phone_regex.match(number):
            return True
        else:
            return False

    def _camelize(self, string):
        def underscore_to_camel(match):
            group = match.group()
            return group[0] + group[2].upper()

        return re.sub(r'[A-Za-z0-9]_[A-Za-z0-9]', underscore_to_camel,
                      string.title())

    def as_dict(self):
        ret = dict()
        for attr in dir(self):
            value = getattr(self, attr)
            if callable(value) or attr.startswith('_') or value is None:
                continue
            key = self._prefix + self._camelize(attr)
            ret[key] = value
        return ret
