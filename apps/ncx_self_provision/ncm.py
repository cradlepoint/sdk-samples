"""
Cradlepoint NCM API class
Created by: Nathan Wiens
Updated by: Jon Gaudu

Overview:
    The purpose of this class is to make it easier for users to interact with
    the Cradlepoint NCM API. Within this class is a set of functions that
    closely matches the available API calls. Full documentation of the
    Cradlepoint NCM API is available at https://developer.cradlepoint.com.

Requirements:
    A set of Cradlepoint NCM API Keys is required to make API calls.
    While the class can be instantiated without supplying API keys,
    any subsequent calls will fail unless the keys are set via the
    set_api_keys() method.

Usage:
    Instantiating the class:
        import ncm
        api_keys = {
           'X-CP-API-ID': 'b89a24a3',
           'X-CP-API-KEY': '4b1d77fe271241b1cfafab993ef0891d',
           'X-ECM-API-ID': 'c71b3e68-33f5-4e69-9853-14989700f204',
           'X-ECM-API-KEY': 'f1ca6cd41f326c00e23322795c063068274caa30'
        }
        n = ncm.NcmClient(api_keys=api_keys)

    Example API call:
        n.get_accounts()

Tips:
    This python class includes a few optimizations to make it easier to
    work with the API. The default record limit is set at 500 instead of
    the Cradlepoint default of 20, which reduces the number of API calls
    required to return large sets of data.

    This can be modified by specifying a "limit parameter":
       n.get_accounts(limit=10)

    You can also return the full list of records in a single array without
    the need for paging by passing limit='all':
       n.get_accounts(limit='all')

    It also has native support for handling any number of "__in" filters
    beyond Cradlepoint's limit of 100. The script automatically chunks
    the list into groups of 100 and combines the results into a single array

"""

from requests import Session
from requests.adapters import HTTPAdapter
from http import HTTPStatus
from urllib3.util.retry import Retry
from datetime import datetime, timedelta
import sys
import os
import json
from typing import Union


def __is_json(test_json):
    """
    Checks if a string is a valid json object
    """
    try:
        json.loads(test_json)
    except ValueError:
        return False
    return True


class BaseNcmClient:
    def __init__(self,
                 log_events=True,
                 logger=None,
                 retries=5,
                 retry_backoff_factor=2,
                 retry_on=None,
                 base_url=None):
        """
        Constructor. Sets up and opens request session.
        :param retries: number of retries on failure. Optional.
        :param retry_backoff_factor: backoff time multiplier for retries.
          Optional.
        :param retry_on: types of errors on which automatic retry will occur.
          Optional.
        :param base_url: # base url for calls. Configurable for testing.
          Optional.
        """
        if retry_on is None:
            retry_on = [
                HTTPStatus.REQUEST_TIMEOUT,
                HTTPStatus.GATEWAY_TIMEOUT,
                HTTPStatus.SERVICE_UNAVAILABLE
            ]
        self.log_events = log_events
        self.logger = logger
        self.session = Session()
        self.adapter = HTTPAdapter(
            max_retries=Retry(total=retries,
                              backoff_factor=retry_backoff_factor,
                              status_forcelist=retry_on,
                              redirect=3
                              )
        )
        self.base_url = base_url
        self.session.mount(self.base_url, self.adapter)
    
    def log(self, level, message):
        """
        Logs messages if self.logEvents is True.
        """
        if self.log_events:
            if self.logger:
                log_level = getattr(self.logger, level)
                log_level(message)
            else:
                print(f"{level}: {message}", file=sys.stderr) 

    def _return_handler(self, status_code, returntext, obj_type):
        """
        Prints returned HTTP request information if self.logEvents is True.
        """
        if str(status_code) == '200':
            return f'{obj_type} operation successful.'
        elif str(status_code) == '201':
            self.log('info', '{0} created Successfully'.format(str(obj_type)))
            return returntext
        elif str(status_code) == '202':
            self.log('info', '{0} accepted Successfully'.format(str(obj_type)))
            return returntext
        elif str(status_code) == '204':
            self.log('info', '{0} deleted Successfully'.format(str(obj_type)))
            return returntext
        elif str(status_code) == '400':
            self.log('error', 'Bad Request')
            return f'ERROR: {status_code}: {returntext}'
        elif str(status_code) == '401':
            self.log('error', 'Unauthorized Access')
            return f'ERROR: {status_code}: {returntext}'
        elif str(status_code) == '404':
            self.log('error', 'Resource Not Found\n')
            return f'ERROR: {status_code}: {returntext}'
        elif str(status_code) == '500':
            self.log('error', 'HTTP 500 - Server Error\n')
            return f'ERROR: {status_code}: {returntext}'
        else:
            self.log('info', f'HTTP Status Code: {status_code} - {returntext}\n')


class NcmClientv2(BaseNcmClient):
    def __init__(self,
                 api_keys=None,
                 log_events=True,
                 logger=None,
                 retries=5,
                 retry_backoff_factor=2,
                 retry_on=None,
                 base_url=None):
        self.v2 = self # for backwards compatibility
        base_url = base_url or os.environ.get("CP_BASE_URL", "https://www.cradlepointecm.com/api/v2")
        super().__init__(log_events=log_events, logger=logger, retries=retries, retry_backoff_factor=retry_backoff_factor, retry_on=retry_on, base_url=base_url)
        if api_keys:
            if self.__validate_api_keys(api_keys):
                self.session.headers.update(api_keys)
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def __validate_api_keys(self, api_keys):
        """
        Checks NCM API Keys are a dictionary containing all necessary keys
        :param api_keys: Dictionary of API credentials. Optional.
        :type api_keys: dict
        :return: True if valid
        """
        if not isinstance(api_keys, dict):
            raise TypeError("API Keys must be passed as a dictionary")

        for key in ('X-CP-API-ID', 'X-CP-API-KEY', 'X-ECM-API-ID', 'X-ECM-API-KEY'):
            if not api_keys.get(key):
                raise KeyError(f"{key} missing. Please ensure all API Keys are present.")

        return True
    
    def __get_json(self, get_url, call_type, params=None):
        """
        Returns full paginated results, and handles chunking "__in" params
        in groups of 100.
        """
        results = []
        __in_keys = 0
        if params['limit'] == 'all':
            params['limit'] = 1000000
        limit = int(params['limit'])

        if params is not None:
            # Ensures that order_by is passed as a comma separated string
            if 'order_by' in params.keys():
                if type(params['order_by']) is list:
                    params['order_by'] = ','.join(
                        str(x) for x in params['order_by'])
                elif type(params['order_by']) is not list and type(
                        params['order_by']) is not str:
                    raise TypeError(
                        "Invalid 'order_by' parameter. "
                        "Must be 'list' or 'str'.")

            for key, val in params.items():
                # Handles multiple filters using __in fields.
                if '__in' in key:
                    __in_keys += 1
                    # Cradlepoint limit of 100 values.
                    # If more than 100 values, break into chunks
                    chunks = self.__chunk_param(val)
                    # For each chunk, get the full results list and
                    # filter by __in parameter
                    for chunk in chunks:
                        # Handles a list of int or list of str
                        chunk_str = ','.join(map(str, chunk))
                        params.update({key: chunk_str})
                        url = get_url
                        while url and (len(results) < limit):
                            ncm = self.session.get(url, params=params)
                            if not (200 <= ncm.status_code < 300):
                                break
                            self._return_handler(ncm.status_code,
                                                  ncm.json()['data'],
                                                  call_type)
                            url = ncm.json()['meta']['next']
                            for d in ncm.json()['data']:
                                results.append(d)

        if __in_keys == 0:
            url = get_url
            while url and (len(results) < limit):
                ncm = self.session.get(url, params=params)
                if not (200 <= ncm.status_code < 300):
                    break
                self._return_handler(ncm.status_code, ncm.json()['data'],
                                      call_type)
                url = ncm.json()['meta']['next']
                for d in ncm.json()['data']:
                    results.append(d)
        return results

    def __parse_kwargs(self, kwargs, allowed_params):
        """
        Increases default return limit to 500,
        and checks for invalid parameters
        """
        params = {k: v for (k, v) in kwargs.items() if k in allowed_params}
        if 'limit' not in params:
            params.update({'limit': '500'})

        bad_params = {k: v for (k, v) in kwargs.items() if
                      k not in allowed_params}
        if len(bad_params) > 0:
            raise ValueError("Invalid parameters: {}".format(bad_params))
        
        self.__validate_api_keys(dict(self.session.headers)) 

        return params

    def __chunk_param(self, param):
        """
        Chunks parameters into groups of 100 per Cradlepoint limit.
        Iterate through chunks with a for loop.
        """
        n = 100

        if type(param) is str:
            param_list = param.split(",")
        elif type(param) is list:
            param_list = param
        else:
            raise TypeError("Invalid param format. Must be str or list.")

        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(param_list), n):
            yield param_list[i:i + n]

    def set_api_keys(self, api_keys):
        """
        Sets NCM API Keys for session.
        :param api_keys: Dictionary of API credentials. Optional.
        :type api_keys: dict
        """
        if self.__validate_api_keys(api_keys):
            self.session.headers.update(api_keys)
        return

    def get_accounts(self, **kwargs):
        """
        Returns accounts with details.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of accounts based on API Key.
        """
        call_type = 'Accounts'
        get_url = '{0}/accounts/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'fields', 'id', 'id__in',
                          'name', 'name__in', 'expand', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_account_by_id(self, account_id):
        """
        This method returns a single account for a given account id.
        :param account_id: ID of account to return
        :return:
        """
        return self.get_accounts(id=account_id)[0]

    def get_account_by_name(self, account_name):
        """
        This method returns a single account for a given account name.
        :param account_name: Name of account to return
        :return:
        """

        return self.get_accounts(name=account_name)[0]

    def create_subaccount_by_parent_id(self, parent_account_id,
                                       subaccount_name):
        """
        This operation creates a new subaccount.
        :param parent_account_id: ID of parent account.
        :param subaccount_name: Name for new subaccount.
        :return:
        """
        call_type = 'Subaccount'
        post_url = '{0}/accounts/'.format(self.base_url)

        post_data = {
            'account': '/api/v1/accounts/{}/'.format(str(parent_account_id)),
            'name': str(subaccount_name)
        }

        ncm = self.session.post(post_url, data=json.dumps(post_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def create_subaccount_by_parent_name(self, parent_account_name,
                                         subaccount_name):
        """
        This operation creates a new subaccount.
        :param parent_account_name: Name of parent account.
        :param subaccount_name: Name for new subaccount.
        :return:
        """
        return self.create_subaccount_by_parent_id(self.get_account_by_name(
            parent_account_name)['id'], subaccount_name)

    def rename_subaccount_by_id(self, subaccount_id, new_subaccount_name):
        """
        This operation renames a subaccount
        :param subaccount_id: ID of subaccount to rename
        :param new_subaccount_name: New name for subaccount
        :return:
        """
        call_type = 'Subaccount'
        put_url = '{0}/accounts/{1}/'.format(self.base_url, str(subaccount_id))

        put_data = {
            "name": str(new_subaccount_name)
        }

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def rename_subaccount_by_name(self, subaccount_name, new_subaccount_name):
        """
        This operation renames a subaccount
        :param subaccount_name: Name of subaccount to rename
        :param new_subaccount_name: New name for subaccount
        :return:
        """
        return self.rename_subaccount_by_id(self.get_account_by_name(
            subaccount_name)['id'], new_subaccount_name)

    def delete_subaccount_by_id(self, subaccount_id):
        """
        This operation deletes a subaccount
        :param subaccount_id: ID of subaccount to delete
        :return:
        """
        call_type = 'Subaccount'
        post_url = '{0}/accounts/{1}'.format(self.base_url, subaccount_id)

        ncm = self.session.delete(post_url)
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def delete_subaccount_by_name(self, subaccount_name):
        """
        This operation deletes a subaccount
        :param subaccount_name: Name of subaccount to delete
        :return:
        """
        return self.delete_subaccount_by_id(self.get_account_by_name(
            subaccount_name)['id'])

    def get_activity_logs(self, **kwargs):
        """
        This method returns NCM activity log information.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Activity Logs'
        get_url = '{0}/activity_logs/'.format(self.base_url)

        allowed_params = ['account', 'created_at__exact', 'created_at__lt',
                          'created_at__lte', 'created_at__gt',
                          'created_at__gte', 'action__timestamp__exact',
                          'action__timestamp__lt',
                          'action__timestamp__lte', 'action__timestamp__gt',
                          'action__timestamp__gte', 'actor__id',
                          'object__id', 'action__id__exact', 'actor__type',
                          'action__type', 'object__type', 'order_by',
                          'limit']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_alerts(self, **kwargs):
        """
        This method gives alert information with associated id.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Alerts'
        get_url = '{0}/alerts/'.format(self.base_url)

        allowed_params = ['account', 'created_at', 'created_at_timeuuid',
                          'detected_at', 'friendly_info', 'info',
                          'router', 'type', 'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_configuration_managers(self, **kwargs):
        """
        A configuration manager is an abstract resource for controlling and
        monitoring config sync on a single device.
        Each device has its own corresponding configuration manager.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Configuration Managers'
        get_url = '{0}/configuration_managers/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'fields', 'id', 'id__in',
                          'router', 'router__in', 'synched',
                          'suspended', 'expand', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_configuration_manager_id(self, router_id, **kwargs):
        """
        A configuration manager is an abstract resource for controlling and
        monitoring config sync on a single device.
        Each device has its own corresponding configuration manager.
        :param router_id: Router ID to query
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Configuration Managers'
        get_url = '{0}/configuration_managers/?router.id={1}&fields=id'.format(
            self.base_url, router_id)

        allowed_params = ['account', 'account__in', 'id', 'id__in', 'router',
                          'router__in', 'synched',
                          'suspended', 'expand', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)[0]['id']

    def update_configuration_managers(self, config_man_id, config_man_json):
        """
        This method updates an configuration_managers for associated id.
        :param config_man_id: ID of the Configuration Manager to modify
        :param config_man_json: JSON of the "configuration" field of the
          configuration manager
        :return:
        """
        call_type = 'Configuration Manager'
        put_url = '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                           config_man_id)

        ncm = self.session.put(put_url, json=config_man_json)
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def patch_configuration_managers(self, router_id, config_man_json):
        """
        This method patches an configuration_managers for associated id.
        :param router_id: ID of router to update
        :param config_man_json: JSON of the "configuration" field of the
          configuration manager
        :return:
        """
        call_type = 'Configuration Manager'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID for router
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        payload = config_man_json

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values

        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def put_configuration_managers(self, router_id, configman_json):
        """
        This method overwrites the configuration for a router with id.
        :param router_id: ID of router to update
        :param configman_json: JSON of the "configuration" field of the
          configuration manager
        :return:
        """
        call_type = 'Configuration Manager'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID for router
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        configman_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        payload = configman_json

        ncm = self.session.put(
            '{0}/configuration_managers/{1}/?fields=configuration'.format(
                self.base_url, str(configman_id)),
            json=payload)  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def patch_group_configuration(self, group_id, config_json):
        """
        This method patches an configuration_managers for associated id.
        :param group_id: ID of group to update
        :param config_json: JSON of the "configuration" field of the
          configuration manager
        :return:
        """
        call_type = 'Configuration Manager'

        payload = config_json

        ncm = self.session.patch(
            '{0}/groups/{1}/'.format(self.base_url, str(group_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def put_group_configuration(self, group_id, config_json):
        """
        This method puts a group configuration for associated group id.
        :param group_id: ID of group to update
        :param config_json: JSON of the "configuration" field of the
          group config
        :return:
        """
        call_type = 'Configuration Manager'

        payload = config_json

        ncm = self.session.put(
            '{0}/groups/{1}/'.format(self.base_url, str(group_id)),
            data=json.dumps(payload))  # put group config with new values
        result = self.__return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def copy_router_configuration(self, src_router_id, dst_router_id):
        """
        Copies the Configuration Manager config of one router to another.
        This function will not copy any passwords as they are encrypted.
        :param src_router_id: Router ID to copy from
        :param dst_router_id: Router ID to copy to
        :return: Should return HTTP Status Code 202 if successful
        """
        call_type = 'Configuration Manager'
        """Get source router existing configuration"""
        src_config = self.get_configuration_managers(router=src_router_id,
                                                     fields='configuration')[0]

        """Strip passwords which aren't stored in plain text"""
        src_config = json.dumps(src_config).replace(', "wpapsk": "*"','').replace('"wpapsk": "*"', '').replace(', "password": "*"', '').replace('"password": "*"', '')

        """Get destination router Configuration Manager ID"""
        dst_config_man_id = \
            self.get_configuration_managers(router=dst_router_id)[0]['id']

        put_url = '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                           dst_config_man_id)

        ncm = self.session.patch(put_url, data=src_config)
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def resume_updates_for_router(self, router_id):
        """
        This method will resume updates for a router in Sync Suspended state.
        :param router_id: ID of router to update
        :return:
        """
        call_type = 'Configuration Manager'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID for router
        response = json.loads(response.content.decode("utf-8"))
        configman_id = response['data'][0]['id']
        payload = {"suspended": False}

        ncm = self.session.put(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(configman_id)),
            json=payload)
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def get_device_app_bindings(self, **kwargs):
        """
        This method gives device app binding information for all device
        app bindings associated with the account.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Device App Bindings'
        get_url = '{0}/device_app_bindings/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'group', 'group__in',
                          'app_version', 'app_version__in',
                          'id', 'id__in', 'state', 'state__in', 'expand',
                          'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_device_app_states(self, **kwargs):
        """
        This method gives device app state information for all device
        app states associated with the account.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Device App States'
        get_url = '{0}/device_app_states/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'router', 'router__in',
                          'app_version', 'app_version__in',
                          'id', 'id__in', 'state', 'state__in', 'expand',
                          'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_device_app_versions(self, **kwargs):
        """
        This method gives device app version information for all device
        app versions associated with the account.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Device App Versions'
        get_url = '{0}/device_app_versions/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'app', 'app__in', 'id',
                          'id__in', 'state', 'state__in',
                          'expand', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_device_apps(self, **kwargs):
        """
        This method gives device app information for all device apps
        associated with the account.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Device Apps'
        get_url = '{0}/device_apps/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'name', 'name__in', 'id',
                          'id__in', 'uuid', 'uuid__in',
                          'expand', 'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_failovers(self, **kwargs):
        """
        This method returns a list of Failover Events for
        a device, group, or account.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Failovers'
        get_url = '{0}/failovers/'.format(self.base_url)

        allowed_params = ['account_id', 'group_id', 'router_id', 'started_at',
                          'ended_at', 'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_firmwares(self, **kwargs):
        """
        This operation gives the list of device firmwares.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Firmwares'
        get_url = '{0}/firmwares/'.format(self.base_url)

        allowed_params = ['id', 'id__in', 'version', 'version__in', 'limit',
                          'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_firmware_for_product_id_by_version(self, product_id,
                                               firmware_name):
        """
        This operation returns firmwares for a given model ID and version name.
        :param product_id: The ID of the product (e.g. 46)
        :param firmware_name: The Firmware Version (e.g. 7.2.0)
        :return:
        """
        for f in self.get_firmwares(version=firmware_name):
            if f['product'] == '{0}/products/{1}/'.format(self.base_url,
                                                          str(product_id)):
                return f
        raise ValueError("Invalid Firmware Version")

    def get_firmware_for_product_name_by_version(self, product_name,
                                                 firmware_name):
        """
        This operation returns firmwares for a given model and version name.
        :param product_name: The Name of the product (e.g. IBR200)
        :param firmware_name: The Firmware Version (e.g. 7.2.0)
        :return:
        """
        product_id = self.get_product_by_name(product_name)['id']
        return self.get_firmware_for_product_id_by_version(product_id,
                                                           firmware_name)

    def get_groups(self, **kwargs):
        """
        This method gives a groups list.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Groups'
        get_url = '{0}/groups/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'id', 'id__in', 'name',
                          'name__in', 'expand', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_group_by_id(self, group_id):
        """
        This method returns a single group.
        :param group_id: The ID of the group.
        :return:
        """
        return self.get_groups(id=group_id)[0]

    def get_group_by_name(self, group_name):
        """
        This method returns a single group.
        :param group_name: The Name of the group.
        :return:
        """
        return self.get_groups(name=group_name)[0]

    def create_group_by_parent_id(self, parent_account_id, group_name,
                                  product_name, firmware_version):
        """
        This operation creates a new group.
        :param parent_account_id: ID of parent account
        :param group_name: Name for new group
        :param product_name: Product model (e.g. IBR200)
        :param firmware_version: Firmware version for group (e.g. 7.2.0)
        :return:
        Example: n.create_group_by_parent_id('123456', 'My New Group',
            'IBR200', '7.2.0')
        """

        call_type = 'Group'
        post_url = '{0}/groups/'.format(self.base_url)

        firmware = self.get_firmware_for_product_name_by_version(
            product_name, firmware_version)

        post_data = {
            'account': '/api/v1/accounts/{}/'.format(str(parent_account_id)),
            'name': str(group_name),
            'product': str(
                self.get_product_by_name(product_name)['resource_url']),
            'target_firmware': str(firmware['resource_url'])
        }

        ncm = self.session.post(post_url, data=json.dumps(post_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def create_group_by_parent_name(self, parent_account_name, group_name,
                                    product_name, firmware_version):
        """
        This operation creates a new group.
        :param parent_account_name: Name of parent account
        :param group_name: Name for new group
        :param product_name: Product model (e.g. IBR200)
        :param firmware_version: Firmware version for group (e.g. 7.2.0)
        :return:
        Example: n.create_group_by_parent_name('Parent Account',
            'My New Group', 'IBR200', '7.2.0')
        """

        return self.create_group_by_parent_id(
            self.get_account_by_name(parent_account_name)['id'], group_name,
            product_name, firmware_version)

    def rename_group_by_id(self, group_id, new_group_name):
        """
        This operation renames a group by specifying ID.
        :param group_id: ID of the group to rename.
        :param new_group_name: New name for the group.
        :return:
        """
        call_type = 'Group'
        put_url = '{0}/groups/{1}/'.format(self.base_url, group_id)

        put_data = {
            "name": str(new_group_name)
        }

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def rename_group_by_name(self, existing_group_name, new_group_name):
        """
        This operation renames a group by specifying name.
        :param existing_group_name: Name of the group to rename
        :param new_group_name: New name for the group.
        :return:
        """
        return self.rename_group_by_id(
            self.get_group_by_name(existing_group_name)['id'], new_group_name)

    def delete_group_by_id(self, group_id):
        """
        This operation deletes a group by specifying ID.
        :param group_id: ID of the group to delete
        :return:
        """
        call_type = 'Group'
        post_url = '{0}/groups/{1}/'.format(self.base_url, group_id)

        ncm = self.session.delete(post_url)
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def delete_group_by_name(self, group_name):
        """
        This operation deletes a group by specifying Name.
        :param group_name: Name of the group to delete
        :return:
        """
        return self.delete_group_by_id(
            self.get_group_by_name(group_name)['id'])

    def get_historical_locations(self, router_id, **kwargs):
        """
        This method returns a list of locations visited by a device.
        :param router_id: ID of the router
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Historical Locations'
        get_url = '{0}/historical_locations/?router={1}'.format(self.base_url,
                                                                router_id)

        allowed_params = ['created_at__gt', 'created_at_timeuuid__gt',
                          'created_at__lte', 'fields', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_historical_locations_for_date(self, router_id, date,
                                          tzoffset_hrs=0, limit='all',
                                          **kwargs):
        """
        This method provides a history of device alerts.
        To receive device alerts, you must enable them through the NCM UI:
        Alerts -> Settings. The info section of the alert is firmware dependent
        and may change between firmware releases.
        :param router_id: ID of the router
        :param date: Date to filter logs. Must be in format "YYYY-mm-dd"
        :type date: str
        :param tzoffset_hrs: Offset from UTC for local timezone
        :type tzoffset_hrs: int
        :param limit: Number of records to return.
          Specifying "all" returns all records. Default all.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """

        d = datetime.strptime(date, '%Y-%m-%d') + timedelta(hours=tzoffset_hrs)
        start = d.strftime("%Y-%m-%dT%H:%M:%S")
        end = (d + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

        call_type = 'Historical Locations'
        get_url = '{0}/historical_locations/?router={1}'.format(self.base_url,
                                                                router_id)

        allowed_params = ['created_at__gt', 'created_at_timeuuid__gt',
                          'created_at__lte', 'fields', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        params.update({'created_at__lte': end,
                       'created_at__gt': start,
                       'limit': limit})

        return self.__get_json(get_url, call_type, params=params)

    def get_locations(self, **kwargs):
        """
        This method gives a list of locations.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Locations'
        get_url = '{0}/locations/'.format(self.base_url)

        allowed_params = ['id', 'id__in', 'router', 'router__in', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def create_location(self, account_id, latitude, longitude, router_id):
        """
        This method creates a location and applies it to a router.
        :param account_id: Account which owns the object
        :param latitude: A device's relative position north or south
        on the Earth's surface, in degrees from the Equator
        :param longitude: A device's relative position east or west
        on the Earth's surface, in degrees from the prime meridian
        :param router_id: Device that the location is associated with
        :return:
        """

        call_type = 'Locations'
        post_url = '{0}/locations/'.format(self.base_url)

        post_data = {
            'account':
                'https://www.cradlepointecm.com/api/v2/accounts/{}/'.format(
                    str(account_id)),
            'accuracy': 0,
            'latitude': latitude,
            'longitude': longitude,
            'method': 'manual',
            'router': 'https://www.cradlepointecm.com/api/v2/routers/{}/'
                .format(str(router_id))
        }

        ncm = self.session.post(post_url, data=json.dumps(post_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def delete_location_for_router(self, router_id):
        """
        This operation deletes the location for a router by ID.
        :param router_id: ID of router for which to remove location.
        :return:
        """
        call_type = 'Locations'

        locations = self.get_locations(router=router_id)
        if locations:
            location_id = locations[0]['id']

            post_url = '{0}/locations/{1}/'.format(self.base_url, location_id)

            ncm = self.session.delete(post_url)
            result = self._return_handler(ncm.status_code, ncm.text,
                                           call_type)
            return result
        else:
            return "NO LOCATION FOUND"

    def get_net_device_health(self, **kwargs):
        """
        This operation gets cellular heath scores, by device.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Net Device Health'
        get_url = '{0}/net_device_health/'.format(self.base_url)

        allowed_params = ['net_device']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_net_device_metrics(self, **kwargs):
        """
        This endpoint is supplied to allow easy access to the latest signal and
          usage data reported by an account's net_devices without querying the
          historical raw sample tables, which are not optimized for a query
          spanning many net_devices at once.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Net Device Metrics'
        get_url = '{0}/net_device_metrics/'.format(self.base_url)

        allowed_params = ['net_device', 'net_device__in', 'update_ts__lt',
                          'update_ts__gt', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_net_devices_metrics_for_wan(self, **kwargs):
        """
        This endpoint is supplied to allow easy access to the latest signal and
          usage data reported by an account's net_devices without querying the
          historical raw sample tables, which are not optimized for a query
          spanning many net_devices at once. Returns data only for
          WAN interfaces.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        ids = []
        for net_device in self.get_net_devices(mode='wan'):
            ids.append(net_device['id'])
        idstring = ','.join(str(x) for x in ids)
        return self.get_net_device_metrics(net_device__in=idstring, **kwargs)

    def get_net_devices_metrics_for_mdm(self, **kwargs):
        """
        This endpoint is supplied to allow easy access to the latest signal and
          usage data reported by an account's net_devices without querying the
          historical raw sample tables, which are not optimized for a query
          spanning many net_devices at once. Returns data only for
          modem interfaces.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        ids = []
        for net_device in self.get_net_devices(is_asset=True):
            ids.append(net_device['id'])
        idstring = ','.join(str(x) for x in ids)
        return self.get_net_device_metrics(net_device__in=idstring, **kwargs)

    def get_net_device_signal_samples(self, **kwargs):
        """
        This endpoint is supplied to allow easy access to the latest signal and
          usage data reported by an account's net_devices without querying the
          historical raw sample tables, which are not optimized for a query
          spanning many net_devices at once.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Get Net Device Signal Samples'
        get_url = '{0}/net_device_signal_samples/'.format(self.base_url)

        allowed_params = ['net_device', 'net_device__in', 'created_at',
                          'created_at__lt', 'created_at__gt',
                          'created_at_timeuuid', 'created_at_timeuuid__in',
                          'created_at_timeuuid__gt',
                          'created_at_timeuuid__gte',
                          'created_at_timeuuid__lt',
                          'created_at_timeuuid__lte',
                          'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_net_device_usage_samples(self, **kwargs):
        """
        This method provides information about the net device's
        overall network traffic.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Net Device Usage Samples'
        get_url = '{0}/net_device_usage_samples/'.format(self.base_url)

        allowed_params = ['net_device', 'net_device__in', 'created_at',
                          'created_at__lt', 'created_at__gt',
                          'created_at_timeuuid', 'created_at_timeuuid__in',
                          'created_at_timeuuid__gt',
                          'created_at_timeuuid__gte',
                          'created_at_timeuuid__lt',
                          'created_at_timeuuid__lte',
                          'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_net_devices(self, **kwargs):
        """
        This method gives a list of net devices.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Net Devices'
        get_url = '{0}/net_devices/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'connection_state',
                          'connection_state__in', 'fields', 'id', 'id__in',
                          'is_asset', 'ipv4_address', 'ipv4_address__in',
                          'mode', 'mode__in', 'router', 'router__in',
                          'expand', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_net_devices_for_router(self, router_id, **kwargs):
        """
        This method gives a list of net devices for a given router.
        :param router_id: ID of the router
        :return:
        """
        return self.get_net_devices(router=router_id, **kwargs)

    def get_net_devices_for_router_by_mode(self, router_id, mode, **kwargs):
        """
        This method gives a list of net devices for a given router,
        filtered by mode (lan/wan).
        :param router_id: ID of router
        :param mode: lan/wan
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        return self.get_net_devices(router=router_id, mode=mode, **kwargs)

    def get_products(self, **kwargs):
        """
        This method gives a list of product information.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Products'
        get_url = '{0}/products/'.format(self.base_url)

        allowed_params = ['id', 'id__in', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_product_by_id(self, product_id):
        """
        This method returns a single product by ID.
        :param product_id: ID of product (e.g. 46)
        :return:
        """
        return self.get_products(id=product_id)[0]

    def get_product_by_name(self, product_name):
        """
        This method returns a single product for a given model name.
        :param product_name: Name of product (e.g. IBR200)
        :return:
        """
        for p in self.get_products():
            if p['name'] == product_name:
                return p
        raise ValueError("Invalid Product Name")

    def reboot_device(self, router_id):
        """
        This operation reboots a device.
        :param router_id: ID of router to reboot
        :return:
        """
        call_type = 'Reboot Device'
        post_url = '{0}/reboot_activity/'.format(self.base_url)

        post_data = {
            'router': '{0}/routers/{1}/'.format(self.base_url, str(router_id))
        }

        ncm = self.session.post(post_url, data=json.dumps(post_data))
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def reboot_group(self, group_id):
        """
        This operation reboots all routers in a group.
        :param group_id: ID of group to reboot
        :return:
        """
        call_type = 'Reboot Group'
        post_url = '{0}/reboot_activity/'.format(self.base_url)

        post_data = {
            'group': '{0}/groups/{1}/'.format(self.base_url, str(group_id))
        }

        ncm = self.session.post(post_url, data=json.dumps(post_data))
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def get_router_alerts(self, **kwargs):
        """
        This method provides a history of device alerts. To receive device
        alerts, you must enable them through the ECM UI: Alerts -> Settings.
        The info section of the alert is firmware dependent and
        may change between firmware releases.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Router Alerts'
        get_url = '{0}/router_alerts/'.format(self.base_url)

        allowed_params = ['router', 'router__in', 'created_at',
                          'created_at__lt', 'created_at__gt',
                          'created_at_timeuuid', 'created_at_timeuuid__in',
                          'created_at_timeuuid__gt',
                          'created_at_timeuuid__gte',
                          'created_at_timeuuid__lt',
                          'created_at_timeuuid__lte',
                          'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_router_alerts_last_24hrs(self, tzoffset_hrs=0, **kwargs):
        """
        This method provides a history of device alerts.
        To receive device alerts, you must enable them through the NCM UI:
        Alerts -> Settings. The info section of the alert is firmware dependent
        and may change between firmware releases.
        :param tzoffset_hrs: Offset from UTC for local timezone
        :type tzoffset_hrs: int
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        d = datetime.utcnow() + timedelta(hours=tzoffset_hrs)
        end = d.strftime("%Y-%m-%dT%H:%M:%S")
        start = (d - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

        call_type = 'Router Alerts'
        get_url = '{0}/router_alerts/'.format(self.base_url)

        allowed_params = ['router', 'router__in']
        params = self.__parse_kwargs(kwargs, allowed_params)

        params.update({'created_at__lt': end,
                       'created_at__gt': start,
                       'order_by': 'created_at_timeuuid',
                       'limit': '500'})

        return self.__get_json(get_url, call_type, params=params)

    def get_router_alerts_for_date(self, date, tzoffset_hrs=0, **kwargs):
        """
        This method provides a history of device alerts.
        To receive device alerts, you must enable them through the NCM UI:
        Alerts -> Settings. The info section of the alert is firmware dependent
        and may change between firmware releases.
        :param date: Date to filter logs. Must be in format "YYYY-mm-dd"
        :type date: str
        :param tzoffset_hrs: Offset from UTC for local timezone
        :type tzoffset_hrs: int
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """

        d = datetime.strptime(date, '%Y-%m-%d') + timedelta(hours=tzoffset_hrs)
        start = d.strftime("%Y-%m-%dT%H:%M:%S")
        end = (d + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

        call_type = 'Router Alerts'
        get_url = '{0}/router_alerts/'.format(self.base_url)

        allowed_params = ['router', 'router__in']
        params = self.__parse_kwargs(kwargs, allowed_params)

        params.update({'created_at__lt': end,
                       'created_at__gt': start,
                       'order_by': 'created_at_timeuuid',
                       'limit': '500'})

        return self.__get_json(get_url, call_type, params=params)

    def get_router_logs(self, router_id, **kwargs):
        """
        This method provides a history of device events.
        To receive device logs you must enable them on the Group settings form.
        Enabling device logs can significantly increase the ECM network traffic
        from the device to the server depending on how quickly the device is
        generating events.
        :param router_id: ID of router from which to grab logs.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Router Logs'
        get_url = '{0}/router_logs/?router={1}'.format(self.base_url,
                                                       router_id)

        allowed_params = ['created_at', 'created_at__lt', 'created_at__gt',
                          'created_at_timeuuid',
                          'created_at_timeuuid__in', 'created_at_timeuuid__gt',
                          'created_at_timeuuid__gte',
                          'created_at_timeuuid__lt',
                          'created_at_timeuuid__lte', 'order_by', 'limit',
                          'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_router_logs_last_24hrs(self, router_id, tzoffset_hrs=0):
        """
        This method provides a history of device events.
        To receive device logs you must enable them on the Group settings form.
        Enabling device logs can significantly increase the ECM network traffic
        from the device to the server depending on how quickly the device is
        generating events.
        :param router_id: ID of router from which to grab logs.
        :param tzoffset_hrs: Offset from UTC for local timezone
        :type tzoffset_hrs: int
        :return:
        """
        d = datetime.utcnow() + timedelta(hours=tzoffset_hrs)
        end = d.strftime("%Y-%m-%dT%H:%M:%S")
        start = (d - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

        call_type = 'Router Logs'
        get_url = '{0}/router_logs/?router={1}'.format(self.base_url,
                                                       router_id)

        params = {'created_at__lt': end, 'created_at__gt': start,
                  'order_by': 'created_at_timeuuid', 'limit': '500'}

        return self.__get_json(get_url, call_type, params=params)

    def get_router_logs_for_date(self, router_id, date, tzoffset_hrs=0):
        """
        This method provides a history of device events.
        To receive device logs you must enable them on the Group settings form.
        Enabling device logs can significantly increase the ECM network traffic
        from the device to the server depending on how quickly the device is
        generating events.
        :param router_id: ID of router from which to grab logs.
        :param date: Date to filter logs. Must be in format "YYYY-mm-dd"
        :type date: str
        :param tzoffset_hrs: Offset from UTC for local timezone
        :type tzoffset_hrs: int
        :return:
        """

        d = datetime.strptime(date, '%Y-%m-%d') + timedelta(hours=tzoffset_hrs)
        start = d.strftime("%Y-%m-%dT%H:%M:%S")
        end = (d + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

        call_type = 'Router Logs'
        get_url = '{0}/router_logs/?router={1}'.format(self.base_url,
                                                       router_id)

        params = {'created_at__lt': end, 'created_at__gt': start,
                  'order_by': 'created_at_timeuuid', 'limit': '500'}

        return self.__get_json(get_url, call_type, params=params)

    def get_router_state_samples(self, **kwargs):
        """
        This method provides information about the connection state of the
        device with the NCM server.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Router State Samples'
        get_url = '{0}/router_state_samples/'.format(self.base_url)

        allowed_params = ['router', 'router__in', 'created_at',
                          'created_at__lt', 'created_at__gt',
                          'created_at_timeuuid', 'created_at_timeuuid__in',
                          'created_at_timeuuid__gt',
                          'created_at_timeuuid__gte',
                          'created_at_timeuuid__lt',
                          'created_at_timeuuid__lte',
                          'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_router_stream_usage_samples(self, **kwargs):
        """
        This method provides information about the connection state of the
        device with the NCM server.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Router Stream Usage Samples'
        get_url = '{0}/router_stream_usage_samples/'.format(self.base_url)

        allowed_params = ['router', 'router__in', 'created_at',
                          'created_at__lt', 'created_at__gt',
                          'created_at_timeuuid', 'created_at_timeuuid__in',
                          'created_at_timeuuid__gt',
                          'created_at_timeuuid__gte',
                          'created_at_timeuuid__lt',
                          'created_at_timeuuid__lte',
                          'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_routers(self, **kwargs):
        """
        This method gives device information with associated id.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        call_type = 'Routers'
        get_url = '{0}/routers/'.format(self.base_url)

        allowed_params = ['account', 'account__in', 'device_type',
                          'device_type__in', 'fields', 'group', 'group__in',
                          'id', 'id__in', 'ipv4_address', 'ipv4_address__in',
                          'mac', 'mac__in', 'name', 'name__in',
                          'reboot_required', 'reboot_required__in', 
                          'serial_number','state', 'state__in', 
                          'state_updated_at__lt', 'state_updated_at__gt', 
                          'updated_at__lt', 'updated_at__gt', 'expand', 
                          'order_by', 'limit', 'offset']
        params = self.__parse_kwargs(kwargs, allowed_params)

        return self.__get_json(get_url, call_type, params=params)

    def get_router_by_id(self, router_id, **kwargs):
        """
        This method gives device information for a given router ID.
        :param router_id: ID of router
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        return self.get_routers(id=router_id, **kwargs)[0]

    def get_router_by_name(self, router_name, **kwargs):
        """
        This method gives device information for a given router name.
        :param router_name: Name of router
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        return self.get_routers(name=router_name, **kwargs)[0]

    def get_routers_for_account(self, account_id, **kwargs):
        """
        This method gives a groups list filtered by account.
        :param account_id: Account ID to filter
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        return self.get_routers(account=account_id, **kwargs)

    def get_routers_for_group(self, group_id, **kwargs):
        """
        This method gives a groups list filtered by group.
        :param group_id: Group ID to filter
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return:
        """
        return self.get_routers(group=group_id, **kwargs)

    def rename_router_by_id(self, router_id, new_router_name):
        """
        This operation renames a router by ID.
        :param router_id: ID of router to rename
        :param new_router_name: New name for router
        :return:
        """
        call_type = 'Router'
        put_url = '{0}/routers/{1}/'.format(self.base_url, router_id)

        put_data = {
            'name': str(new_router_name)
        }

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def rename_router_by_name(self, existing_router_name, new_router_name):
        """
        This operation renames a router by name.
        :param existing_router_name: Name of router to rename
        :param new_router_name: New name for router
        :return:
        """
        return self.rename_router_by_id(
            self.get_router_by_name(existing_router_name)['id'], new_router_name)

    def assign_router_to_group(self, router_id, group_id):
        """
        This operation assigns a router to a group.
        :param router_id: ID of router to move.
        :param group_id: ID of destination group.
        :return:
        """
        call_type = "Router"

        put_url = '{0}/routers/{1}/'.format(self.base_url, str(router_id))

        put_data = {
            "group": 'https://www.cradlepointecm.com/api/v2/groups/{}/'.format(
                group_id)
        }

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def remove_router_from_group(self, router_id=None, router_name=None):
        """
        This operation removes a router from its group.
        Either the ID or the name must be specified.
        :param router_id: ID of router to move.
        :param router_name: Name of router to move
        :return:
        """
        call_type = "Router"
        if not router_id and not router_name:
            return "ERROR: Either Router ID or Router Name must be specified."
        if not router_id:
            router_id = self.get_router_by_name(router_name)['id']

        put_url = '{0}/routers/{1}/'.format(self.base_url, str(router_id))

        put_data = {
            "group": None
        }

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        if ncm.status_code == 201 or ncm.status_code == 202:
            self.log('info', 'Router Modified Successfully')
            return None
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def assign_router_to_account(self, router_id, account_id):
        """
        This operation assigns a router to an account.
        :param router_id: ID of router to move.
        :param account_id: ID of destination account.
        :return:
        """
        call_type = "Routers"

        put_url = '{0}/routers/{1}/'.format(self.base_url, str(router_id))

        put_data = {
            "account":
                'https://www.cradlepointecm.com/api/v2/accounts/{}/'.format(
                    account_id)
        }

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def delete_router_by_id(self, router_id):
        """
        This operation deletes a router by ID.
        :param router_id: ID of router to delete.
        :return:
        """
        call_type = 'Router'
        post_url = '{0}/routers/{1}/'.format(self.base_url, router_id)

        ncm = self.session.delete(post_url)
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def delete_router_by_name(self, router_name):
        """
        This operation deletes a router by name.
        :param router_name: Name of router to delete
        :return:
        """
        return self.delete_router_by_id(
            self.get_router_by_name(router_name)['id'])

    def create_speed_test(self, net_device_ids: list, account_id=None,
                          host="netperf-west.bufferbloat.net",
                          max_test_concurrency=5, port=12865, size=None,
                          test_timeout=10, test_type="TCP Download", time=10):
        """
        This method creates a speed test using Netperf.

        Usage Example:
        n.create_speed_test([12345])

        :param account_id: Account in which to create the speed_test record.
        :param host: URL of Speedtest Server.
        :param max_test_concurrency: Number of maximum simultaneous tests to server (1-50).
        :param net_device_ids: List of net_device IDs (up to 10,000 net_device IDs per request).
        :param port: TCP port for test.
        :param size: Number of bytes to transfer.
        :param test_timeout: Test timeout in seconds.
        :param test_type: TCP Download, TCP Upload, TCP Latency
        :param time: Test time
        :return:
        """
        call_type = 'Speed Test'
        post_url = '{0}/speed_test/'.format(self.base_url)

        if account_id is None:
            account_id = self.get_accounts()[0]['id']

        post_data = {
            "account": f"https://www.cradlepointecm.com/api/v2/accounts/{account_id}/",
            "config": {
                "host": host,
                "max_test_concurrency": max_test_concurrency,
                "net_device_ids": net_device_ids,
                "port": port,
                "size": size,
                "test_timeout": test_timeout,
                "test_type": test_type,
                "time": time
            }
        }

        ncm = self.session.post(post_url, data=json.dumps(post_data))
        if ncm.status_code == 201:
            return ncm.json()
        else:
            return ncm.text

    def create_speed_test_mdm(self, router_id, account_id=None,
                          host="netperf-west.bufferbloat.net",
                          max_test_concurrency=5, port=12865, size=None,
                          test_timeout=10, test_type="TCP Download", time=10):
        """
        This method creates a speed test using Netperf for all connected
        modems by specifying a router_id. This is helpful when the desired
        net_device_id(s) are not known

        Usage Example:
        n.create_speed_test_mdm(12345)

        :param account_id: Account in which to create the speed_test record.
        :param host: URL of Speedtest Server.
        :param max_test_concurrency: Number of maximum simultaneous tests to server (1-50).
        :param router_id: Router ID to test.
        :param port: TCP port for test.
        :param size: Number of bytes to transfer.
        :param test_timeout: Test timeout in seconds.
        :param test_type: TCP Download, TCP Upload, TCP Latency
        :param time: Test time
        :return:
        """

        net_devices = self.get_net_devices_for_router(router_id, connection_state='connected', is_asset=True)
        net_device_ids = [int(x["id"]) for x in net_devices]
        speed_test = self.create_speed_test(net_device_ids=net_device_ids,
                                            account_id=account_id,
                                            host=host,
                                            max_test_concurrency=max_test_concurrency,
                                            port=port,
                                            size=size,
                                            test_timeout=test_timeout,
                                            test_type=test_type,
                                            time=time)
        return speed_test

    def get_speed_test(self, speed_test_id, **kwargs):
        """
        This method gets the status/results of a created speed test.

        Usage Example:
        speed_test = n.create_speed_test([123456])
        n.get_speed_test(speed_test['id'])

        :param speed_test_id: ID of a speed_test record
        :return:
        """
        call_type = 'Speed Test'
        get_url = '{0}/speed_test/{1}/'.format(self.base_url, speed_test_id)

        return self.session.get(get_url).json()


    def set_lan_ip_address(self, router_id, lan_ip, netmask=None,
                           network_id=0):
        """
        This method sets the Primary LAN IP Address for a given router id.
        :param router_id: ID of router to update
        :param lan_ip: LAN IP Address. (e.g. 192.168.1.1)
        :param netmask: Subnet mask. (e.g. 255.255.255.0)
        :param network_id: The ID of the network to update.
          Numbering starts from 0. Defaults to Primary LAN.
        :return:
        """
        call_type = 'LAN IP Address'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        if netmask:
            payload = {
                "configuration": [
                    {
                        "lan": {
                            network_id: {
                                "ip_address": lan_ip,
                                "netmask": netmask
                            }
                        }
                    },
                    []
                ]
            }

        else:
            payload = {
                "configuration": [
                    {
                        "lan": {
                            network_id: {
                                "ip_address": lan_ip
                            }
                        }
                    },
                    []
                ]
            }

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def set_custom1(self, router_id, text):
        """
        This method updates the Custom1 field in NCM for a given router id.
        :param router_id: ID of router to update.
        :param text: The text to set for the field
        :return:
        """
        call_type = "NCM Field Update"

        put_url = '{0}/routers/{1}/'.format(self.base_url, str(router_id))

        put_data = {
            "custom1": str(text)
        }

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def set_custom2(self, router_id, text):
        """
        This method updates the Custom2 field in NCM for a given router id.
        :param router_id: ID of router to update.
        :param text: The text to set for the field
        :return:
        """
        call_type = "NCM Field Update"

        put_url = '{0}/routers/{1}/'.format(self.base_url, str(router_id))

        put_data = {
            "custom2": str(text)
        }

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def set_admin_password(self, router_id: int, new_password: str):
        """
        This method sets the local admin password for a router.
        :param router_id: ID of router to update
        :param new_password: Cleartext password to assign
        :return:
        """
        call_type = 'Admin Password'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        payload = {
            "configuration": [
                {
                    "system": {
                        "users": {
                            "0": {
                                "password": new_password
                            }
                        }
                    }
                },
                []
            ]
        }

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def set_router_name(self, router_id: int, new_router_name: str):
        """
        This method sets the local admin password for a router.
        :param router_id: ID of router to update
        :param new_router_name: Name/System ID to set
        :return:
        """
        call_type = 'Router Name'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        payload = {
            "configuration": [
                {
                    "system": {
                        "system_id": new_router_name
                    }
                },
                []
            ]
        }

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def set_router_description(self, router_id: int, new_router_description: str):
        """
        This method sets the local admin password for a router.
        :param router_id: ID of router to update
        :param new_router_description: Description string to set
        :return:
        """
        call_type = 'Description'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        payload = {
            "configuration": [
                {
                    "system": {
                        "desc": new_router_description
                    }
                },
                []
            ]
        }

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def set_router_asset_id(self, router_id: int, new_router_asset_id: str):
        """
        This method sets the local admin password for a router.
        :param router_id: ID of router to update
        :param new_router_asset_id: Asset ID string to set
        :return:
        """
        call_type = 'Asset ID'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        payload = {
            "configuration": [
                {
                    "system": {
                        "asset_id": new_router_asset_id
                    }
                },
                []
            ]
        }

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def set_ethernet_wan_ip(self, router_id: int, new_wan_ip: str,
                            new_netmask: str = None, new_gateway: str = None):
        """
        This method sets the Ethernet WAN IP Address for a given router id.
        :param router_id: ID of router to update
        :param new_wan_ip: IP Address to assign to Ethernet WAN
        :param new_netmask: Network Mask in dotted decimal notation (optional)
        :param new_gateway: IP of gateway (optional)
        :return:
        """
        call_type = 'Etheret WAN IP Address'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        ip_override = {
            "ip_address": new_wan_ip
        }

        if new_netmask:
            ip_override['netmask'] = new_netmask

        if new_gateway:
            ip_override['gateway'] = new_gateway

        payload = {
            "configuration": [
                {
                    "wan": {
                        "rules2": {
                            "0": {
                                "ip_override": ip_override
                            }
                        }
                    }
                },
                []
            ]
        }

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def add_custom_apn(self, router_id: int, new_carrier: str, new_apn: str):
        """
        This method adds a new APN to the Advanced APN configuration
        :param router_id: ID of router to update
        :param new_carrier: Home Carrier / PLMN
        :param new_apn: APN
        :return:
        """
        call_type = 'Custom APN'

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id,configuration'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        new_apn_id = 0
        try:
            if response['data'][0]['configuration'][0]['wan']:
                if response['data'][0]['configuration'][0]['wan']['custom_apns']:
                    new_apn_id = len(response['data'][0]['configuration'][0]['wan']['custom_apns'])
        except KeyError:
            pass

        payload = {
            "configuration": [
                {
                    "wan": {
                        "custom_apns": {
                            new_apn_id: {
                                "apn": new_apn,
                                "carrier": new_carrier
                            }
                        }
                    }
                },
                []
            ]
        }

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                     str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result
    

    def set_ncm_api_keys_by_router(self, router_id=None, router_name=None, x_ecm_api_id: str = None, x_ecm_api_key: str = None, x_cp_api_id: str = None, x_cp_api_key: str = None, bearer_token: str = ''):
        """
        This method sets NCM API keys using the router's certificate management configuration
        :param router_id: ID of router to update (optional if router_name is provided)
        :param router_name: Name of router to update (optional if router_id is provided)
        :param x_ecm_id: ECM ID
        :param x_ecm_api_key: ECM API Key
        :param x_cp_api_id: CP API ID
        :param x_cp_api_key: CP API Key
        :param bearer_token: Bearer Token
        :return:
        """
        call_type = 'Set NCM API Keys'

        if not router_id and not router_name:
            raise Exception("Either router_id or router_name must be provided")
        
        if router_name and not router_id:
            try:
                router_id = self.get_router_by_name(router_name)['id']
            except Exception as e:
                raise Exception(f"Router with name '{router_name}' not found: {str(e)}")

        response = self.session.get(
            '{0}/configuration_managers/?router.id={1}&fields=id,configuration'.format(
                self.base_url,
                str(router_id)))  # Get Configuration Managers ID
        response = json.loads(response.content.decode(
            "utf-8"))  # Decode the response and make it a dictionary
        config_man_id = response['data'][0][
            'id']  # get the Configuration Managers ID from response

        x509 = "-----BEGIN CERTIFICATE-----\nMIIB0jCCATugAwIBAgIUIF7Bygk4C0l0ikNv00u98unXZ9kwDQYJKoZIhvcNAQEL\nBQAwFzEVMBMGA1UEAwwMTmV0Q2xvdWQgQVBJMB4XDTI1MDYwNDA5MjYzNloXDTM1\nMDYwMzA5MjYzNlowFzEVMBMGA1UEAwwMTmV0Q2xvdWQgQVBJMIGfMA0GCSqGSIb3\nDQEBAQUAA4GNADCBiQKBgQDHWAtI42kixQBU9yZdiTmakxlj1OGfXlYGYDTMr/Q7\neFRZHLxJwIwrfV4UjJSvXkeo9ui1JNXzfQzDwZXdJKEdFM0fBpu9TD/cyetz9lCs\nh5YL1aC0IcH/liZwGt/z2X4snqe3KADHjy8Dl/5ib16vTC/FuRm02Bf8wVJ0c/sr\nhwIDAQABoxswGTAJBgNVHREEAjAAMAwGA1UdEwEB/wQCMAAwDQYJKoZIhvcNAQEL\nBQADgYEAB5UavmWqkT7MXnt2/RE2qdtoTw4PfWIo+I2O7FAwJmHISubp3LW1vCn0\nRIsnyscH+BZmQkZOk3AYhLikgSky64HRHK32HXrLr79ku4as0drJzxuVOOKJn1+6\nDiNWTpAhzT55WU3fZ9H6FRvfEls0ZtLia/yiZ60rH01RO0lo2bs=\n-----END CERTIFICATE-----\n"
        payload = {
            "configuration": [
                {
                    "certmgmt": {
                        "certs": {
                            "00000000-abcd-1234-abcd-123456789000": {
                                "_id_": "00000000-abcd-1234-abcd-123456789000",
                                "key": x_ecm_api_id,
                                "name": "X-ECM-API-ID",
                                "x509": x509
                            },
                            "00000001-abcd-1234-abcd-123456789000": {
                                "_id_": "00000001-abcd-1234-abcd-123456789000",
                                "key": x_ecm_api_key,
                                "name": "X-ECM-API-KEY",
                                "x509": x509
                            },
                            "00000002-abcd-1234-abcd-123456789000": {
                                "_id_": "00000002-abcd-1234-abcd-123456789000",
                                "key": x_cp_api_id,
                                "name": "X-CP-API-ID",
                                "x509": x509
                            },
                            "00000003-abcd-1234-abcd-123456789000": {
                                "_id_": "00000003-abcd-1234-abcd-123456789000",
                                "key": x_cp_api_key,
                                "name": "X-CP-API-KEY",
                                "x509": x509
                            },
                            "00000004-abcd-1234-abcd-123456789000": {
                                "_id_": "00000004-abcd-1234-abcd-123456789000",
                                "key": bearer_token,
                                "name": "Bearer Token",
                                "x509": x509
                            }
                        }
                    }
                },
                []
            ]
        }

        ncm = self.session.patch(
            '{0}/configuration_managers/{1}/'.format(self.base_url,
                                                        str(config_man_id)),
            data=json.dumps(payload))  # Patch indie config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def set_ncm_api_keys_by_group(self, group_id=None, group_name=None, x_ecm_api_id: str = None, x_ecm_api_key: str = None, x_cp_api_id: str = None, x_cp_api_key: str = None, bearer_token: str = ''):
        """
        This method sets NCM API keys using the group's certificate management configuration
        :param group_id: ID of group to update (optional if group_name is provided)
        :param group_name: Name of group to update (optional if group_id is provided)
        :param x_ecm_id: ECM ID
        :param x_ecm_api_key: ECM API Key
        :param x_cp_api_id: CP API ID
        :param x_cp_api_key: CP API Key
        :param bearer_token: Bearer Token
        :return:
        """
        call_type = 'Set NCM API Keys'

        if not group_id and not group_name:
            raise Exception("Either group_id or group_name must be provided")
        
        if group_name and not group_id:
            try:
                group_id = self.get_group_by_name(group_name)['id']
            except Exception as e:
                raise Exception(f"Group with name '{group_name}' not found: {str(e)}")

        x509 = "-----BEGIN CERTIFICATE-----\nMIIB0jCCATugAwIBAgIUIF7Bygk4C0l0ikNv00u98unXZ9kwDQYJKoZIhvcNAQEL\nBQAwFzEVMBMGA1UEAwwMTmV0Q2xvdWQgQVBJMB4XDTI1MDYwNDA5MjYzNloXDTM1\nMDYwMzA5MjYzNlowFzEVMBMGA1UEAwwMTmV0Q2xvdWQgQVBJMIGfMA0GCSqGSIb3\nDQEBAQUAA4GNADCBiQKBgQDHWAtI42kixQBU9yZdiTmakxlj1OGfXlYGYDTMr/Q7\neFRZHLxJwIwrfV4UjJSvXkeo9ui1JNXzfQzDwZXdJKEdFM0fBpu9TD/cyetz9lCs\nh5YL1aC0IcH/liZwGt/z2X4snqe3KADHjy8Dl/5ib16vTC/FuRm02Bf8wVJ0c/sr\nhwIDAQABoxswGTAJBgNVHREEAjAAMAwGA1UdEwEB/wQCMAAwDQYJKoZIhvcNAQEL\nBQADgYEAB5UavmWqkT7MXnt2/RE2qdtoTw4PfWIo+I2O7FAwJmHISubp3LW1vCn0\nRIsnyscH+BZmQkZOk3AYhLikgSky64HRHK32HXrLr79ku4as0drJzxuVOOKJn1+6\nDiNWTpAhzT55WU3fZ9H6FRvfEls0ZtLia/yiZ60rH01RO0lo2bs=\n-----END CERTIFICATE-----\n"
        payload = {
            "configuration": [
                {
                    "certmgmt": {
                        "certs": {
                            "00000000-abcd-1234-abcd-123456789000": {
                                "_id_": "00000000-abcd-1234-abcd-123456789000",
                                "key": x_ecm_api_id,
                                "name": "X-ECM-API-ID",
                                "x509": x509
                            },
                            "00000001-abcd-1234-abcd-123456789000": {
                                "_id_": "00000001-abcd-1234-abcd-123456789000",
                                "key": x_ecm_api_key,
                                "name": "X-ECM-API-KEY",
                                "x509": x509
                            },
                            "00000002-abcd-1234-abcd-123456789000": {
                                "_id_": "00000002-abcd-1234-abcd-123456789000",
                                "key": x_cp_api_id,
                                "name": "X-CP-API-ID",
                                "x509": x509
                            },
                            "00000003-abcd-1234-abcd-123456789000": {
                                "_id_": "00000003-abcd-1234-abcd-123456789000",
                                "key": x_cp_api_key,
                                "name": "X-CP-API-KEY",
                                "x509": x509
                            },
                            "00000004-abcd-1234-abcd-123456789000": {
                                "_id_": "00000004-abcd-1234-abcd-123456789000",
                                "key": bearer_token,
                                "name": "Bearer Token",
                                "x509": x509
                            }
                        }
                    }
                },
                []
            ]
        }

        ncm = self.session.patch(
            '{0}/groups/{1}/'.format(self.base_url, str(group_id)),
            data=json.dumps(payload))  # Patch group config with new values
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def set_router_fields(self, router_id: int, name: str = None, description: str = None, asset_id: str = None, custom1: str = None, custom2: str = None):
        """
        This method sets multiple fields for a router.
        :param router_id: ID of router to update
        :param name: Name/System ID to set
        :param description: Description string to set
        :param asset_id: Asset ID string to set
        :param custom1: Custom1 field to set
        :param custom2: Custom2 field to set
        :return:
        """
        call_type = 'Router Fields'

        put_url = '{0}/routers/{1}/'.format(self.base_url, str(router_id))

        put_data = {}
        for k,v in (('name', name), ('description', description), ('asset_id', asset_id), ('custom1', custom1), ('custom2', custom2)):
            if v is not None:
                put_data[k] = v

        ncm = self.session.put(put_url, data=json.dumps(put_data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

class NcmClientv3(BaseNcmClient):
    """
    This NCM Client class provides functions for interacting with =
    the Cradlepoint NCM API. Full documentation of the Cradlepoint API can be
    found at: https://developer.cradlepoint.com
    """

    def __init__(self,
                 api_key=None,
                 log_events=False,
                 logger=None,
                 retries=5,
                 retry_backoff_factor=2,
                 retry_on=None,
                 base_url=None):
        """
        Constructor. Sets up and opens request session.
        :param api_key: API Bearer token (without the "Bearer" text).
          Optional, but must be set before calling functions.
        :type api_key: str
        :param log_events: if True, HTTP status info will be printed. False by default
        :type log_events: bool
        :param retries: number of retries on failure. Optional.
        :param retry_backoff_factor: backoff time multiplier for retries.
          Optional.
        :param retry_on: types of errors on which automatic retry will occur.
          Optional.
        :param base_url: # base url for calls. Configurable for testing.
          Optional.
        """
        self.v3 = self # For backwards compatibility
        base_url = base_url or os.environ.get("CP_BASE_URL_V3", "https://api.cradlepointecm.com/api/v3")
        super().__init__(log_events, logger, retries, retry_backoff_factor, retry_on, base_url)
        if api_key:
            token = {'Authorization': f'Bearer {api_key}'}
            self.session.headers.update(token)
        self.session.headers.update({
            'Content-Type': 'application/vnd.api+json',
            'Accept': 'application/vnd.api+json'
        })

    def __get_json(self, get_url, call_type, params=None):
        """
        Returns full paginated results
        """
        results = []

        if params is not None and "limit" in params:
            limit = params['limit']
            if limit == 0:
                limit = 1000000
            if params['limit'] > 50 or params['limit'] == 0:
                params['page[size]'] = 50
            else:
                params['page[size]'] = params['limit']
        else:
            limit = 50

        url = get_url

        while url and (len(results) < limit):
            ncm = self.session.get(url, params=params)
            if not (200 <= ncm.status_code < 300):
                return self._return_handler(ncm.status_code, ncm.json(), call_type)
            data = ncm.json()['data']
            if isinstance(data, list):
                self._return_handler(ncm.status_code, data, call_type)
                for d in data:
                    results.append(d)
            else:
                results.append(data)
            if "links" in ncm.json():
                url = ncm.json()['links']['next']
            else:
                url = None

        if params is not None and "filter[fields]" in params.keys():
            data = []
            fields = params['filter[fields]'].split(",")
            for result in results:
                items = {}
                for k, v in result['attributes'].items():
                    if k in fields:
                        items[k] = v
                data.append(items)
            return data

        return results


    def __parse_kwargs(self, kwargs, allowed_params):
        """
        Checks for invalid parameters and missing API Keys, and handles "filter" fields
        """
        if 'search' in kwargs:
            return self.__parse_search_kwargs(kwargs, allowed_params)

        bad_params = {k: v for (k, v) in kwargs.items() if
                      k not in allowed_params if ("search" not in k and "filter" not in k and "sort" not in k)}
        if len(bad_params) > 0:
            raise ValueError("Invalid parameters: {}".format(bad_params))

        if 'Authorization' not in self.session.headers:
            raise KeyError(
                "API key missing. "
                "Please set API key before making API calls.")

        params = {}

        for key, val in kwargs.items():
            if "search" in key or "filter" in key or "sort" in key or "limit" in key:
                params[key] = val

            elif "__" in key:
                split_key = key.split("__")
                params[f'filter[{split_key[0]}][{split_key[1]}]'] = val
            else:
                params[f'filter[{key}]'] = val

        return params

    def __parse_search_kwargs(self, kwargs, allowed_params):
        """
        Checks for invalid parameters and missing API Keys, and handles "search" fields
        """

        bad_params = {k: v for (k, v) in kwargs.items() if
                      k not in allowed_params if ("search" not in k and "filter" not in k and "sort" not in k)}
        if len(bad_params) > 0:
            raise ValueError("Invalid parameters: {}".format(bad_params))

        if 'Authorization' not in self.session.headers:
            raise KeyError(
                "API key missing. "
                "Please set API key before making API calls.")

        params = {}

        for key, val in kwargs.items():
            if "filter" in key or "sort" in key or "limit" in key:
                params[key] = val
            elif "fields" in key:
                params[f'filter[{key}]'] = val
            else:
                if "search" not in key:
                    params[f'search[{key}]'] = val

        return params

    def __parse_put_kwargs(self, kwargs, allowed_params):
        """
        Checks for invalid parameters and missing API Keys, and handles "filter" fields
        """

        bad_params = {k: v for (k, v) in kwargs.items() if
                      k not in allowed_params if ("search" not in k and "filter" not in k and "sort" not in k)}
        if len(bad_params) > 0:
            raise ValueError("Invalid parameters: {}".format(bad_params))

        if 'Authorization' not in self.session.headers:
            raise KeyError(
                "API key missing. "
                "Please set API key before making API calls.")

        return kwargs

    def set_api_key(self, api_key):
        """
        Sets NCM API Keys for session.
        :param api_key: API Bearer token (without the "Bearer" prefix).
        :type api_key: str
        """
        if api_key:
            token = {'Authorization': f'Bearer {api_key}'}
            self.session.headers.update(token)
        return

    def get_users(self, **kwargs):
        """
        Returns users with details.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of users with details.
        """
        call_type = 'Users'
        get_url = f'{self.base_url}/beta/users'

        allowed_params = ['email',
                          'email__not',
                          'first_name',
                          'first_name__ne',
                          'id',
                          'is_active__ne',
                          'last_login',
                          'last_login__lt',
                          'last_login__lte',
                          'last_login__gt',
                          'last_login__gte',
                          'last_login__ne',
                          'last_name',
                          'last_name__ne',
                          'pending_email',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def create_user(self, email, first_name, last_name, **kwargs):
        """
        Creates a user.
        :param email: Email address
        :type email: str
        :param first_name: First name
        :type first_name: str
        :param last_name: Last name
        :type last_name: str
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: User creation result.
        """
        call_type = 'User'
        post_url = f'{self.base_url}/beta/users'

        allowed_params = ['is_active',
                          'last_login',
                          'pending_email']
        params = self.__parse_kwargs(kwargs, allowed_params)
        params['email'] = email
        params['first_name'] = first_name
        params['last_name'] = last_name

        """GET TENANT ID"""
        t = self.get_subscriptions(limit=1)

        data = {
            "data": {
                "type": "users",
                "attributes": params,
                "relationships": {
                    "tenant": {
                        "data": [t[0]['relationships']['tenants']['data']]
                    }
                }
            }
        }

        ncm = self.session.post(post_url, data=json.dumps(data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def update_user(self, email, **kwargs):
        """
        Updates a user's date.
        :param email: Email address
        :type email: str
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: User update result.
        """
        call_type = 'Users'

        user = self.get_users(email=email)[0]
        user.pop('links')

        put_url = f'{self.base_url}/beta/users/{user["id"]}'

        allowed_params = ['first_name',
                          'last_name',
                          'is_active',
                          'user_id',
                          'last_login',
                          'pending_email']
        params = self.__parse_kwargs(kwargs, allowed_params)

        for k, v in params.items():
            user['attributes'][k] = v

        user = {"data": user}

        ncm = self.session.put(put_url, data=json.dumps(user))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def delete_user(self, email, **kwargs):
        """
        Updates a user's date.
        :param email: Email address
        :type email: str
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: None unless error.
        """
        call_type = 'Users'

        user = self.get_users(email=email)[0]
        user.pop('links')

        delete_url = f'{self.base_url}/beta/users/{user["id"]}'

        ncm = self.session.delete(delete_url)
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def get_asset_endpoints(self, **kwargs):
        """
        Returns assets with details.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of asset endpoints (routers) with details.
        """
        call_type = 'Asset Endpoints'
        get_url = f'{self.base_url}/asset_endpoints'

        allowed_params = ['id',
                          'hardware_series',
                          'hardware_series_key',
                          'mac_address',
                          'serial_number',
                          'fields',
                          'limit',
                          'sort']
        
        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_subscriptions(self, **kwargs):
        """
        Returns subscriptions with details.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of subscriptions with details.
        """
        call_type = 'Subscriptions'
        get_url = f'{self.base_url}/subscriptions'

        allowed_params = ['end_time',
                          'end_time__lt',
                          'end_time__lte',
                          'end_time__gt',
                          'end_time__gte',
                          'end_time__ne',
                          'id',
                          'name',
                          'quantity',
                          'start_time',
                          'start_time__lt',
                          'start_time__lte',
                          'start_time__gt',
                          'start_time__gte',
                          'start_time__ne',
                          'tenant',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)
    
    def regrade(self, subscription_id, mac, action="UPGRADE"):
        """ 
        Applies a subscription to an asset.
        :param subscription_id: ID of the subscription to apply. See https://developer.cradlepoint.com/ for list of subscriptions.
        :param mac: MAC address of the asset to apply the subscription to. Can also be a list.
        :param action: Action to take. Default is "UPGRADE". Can also be "DOWNGRADE".
        """

        call_type = 'Subscription'
        post_url = f'{self.base_url}/asset_endpoints/regrades'

        payload = {
            "atomic:operations": []
        }
        mac = mac if isinstance(mac, list) else [mac]
        for smac in mac:
            data = {
                "op": "add",
                "data": {
                    "type": "regrades",
                    "attributes": {
                        "action": action,
                        "subscription_type": subscription_id,
                        "mac_address": smac.replace(':','') if len(smac) == 17 else smac
                    }
                }
            }
            payload["atomic:operations"].append(data)

        ncm = self.session.post(post_url, json=payload)
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def get_regrades(self, **kwargs):
        """
        Returns regrade jobs with details.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of regrades with details.
        """
        call_type = 'Subscription'
        get_url = f'{self.base_url}/asset_endpoints/regrades'

        allowed_params = ["id", 
                    "action_id", 
                    "mac_address", 
                    "created_at", 
                    "action", 
                    "subcription_type", 
                    "status", 
                    "error_code"]

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_private_cellular_networks(self, **kwargs):
        """
        Returns information about your private cellular networks.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of PCNs with details.
        """
        call_type = 'Private Cellular Networks'
        get_url = f'{self.base_url}/beta/private_cellular_networks'

        allowed_params = ['core_ip',
                          'created_at',
                          'created_at__lt',
                          'created_at__lte',
                          'created_at__gt',
                          'created_at__gte',
                          'created_at__ne',
                          'ha_enabled',
                          'id',
                          'mobility_gateways',
                          'mobility_gateway_virtual_ip',
                          'name',
                          'state',
                          'status',
                          'tac',
                          'type',
                          'updated_at',
                          'updated_at__lt',
                          'updated_at__lte',
                          'updated_at__gt',
                          'updated_at__gte',
                          'updated_at__ne',
                          'fields',
                          'limit',
                          'sort']
        
        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_private_cellular_network(self, network_id, **kwargs):
        """
        Returns information about a private cellular network.
        :param network_id: ID of the private_cellular_networks record
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: An individual PCN network with details.
        """
        call_type = 'Private Cellular Networks'
        get_url = f'{self.base_url}/beta/private_cellular_networks/{network_id}'

        allowed_params = ['name',
                          'segw_ip',
                          'ha_enabled',
                          'mobility_gateway_virtual_ip',
                          'state',
                          'status',
                          'tac',
                          'created_at',
                          'updated_at',
                          'fields']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def update_private_cellular_network(self, id=None, name=None, **kwargs):
        """
        Make changes to a private cellular network.
        :param id: PCN network ID. Specify either this or name.
        :type id: str
        :param name: PCN network name
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: PCN update result.
        """
        call_type = 'Private Cellular Network'

        if not id and not name:
            return "ERROR: no network specified. Must specify either network_id or network_name"

        if id:
            net = self.get_private_cellular_networks(id=id)[0]
        elif name:
            net = self.get_private_cellular_networks(name=name)[0]

        if name:
            kwargs['name'] = name

        net.pop('links')

        put_url = f'{self.base_url}/beta/private_cellular_networks/{net["id"]}'

        allowed_params = ['core_ip',
                          'ha_enabled',
                          'id',
                          'mobility_gateways',
                          'mobility_gateway_virtual_ip',
                          'name',
                          'state',
                          'status',
                          'tac',
                          'type']
        params = self.__parse_put_kwargs(kwargs, allowed_params)

        for k, v in params.items():
            net['attributes'][k] = v

        data = {"data": net}

        ncm = self.session.put(put_url, data=json.dumps(data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def create_private_cellular_network(self, name, core_ip, ha_enabled=False, mobility_gateway_virtual_ip=None, mobility_gateways=None):
        """
        Make changes to a private cellular network.
        :param name: Name of the networks.
        :type name: str
        :param core_ip: IP address to reach core network.
        :type core_ip: str
        :param ha_enabled: High availability (HA) of network.
        :type ha_enabled: bool
        :param mobility_gateway_virtual_ip: Virtual IP address to reach core when HA is enabled. Nullable.
        :type mobility_gateway_virtual_ip: str
        :param mobility_gateways: Comma separated list of private_cellular_cores IDs to add as mobility gateways. Nullable.
        :type mobility_gateways: str
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: Create PCN result..
        """
        call_type = 'Private Cellular Network'

        post_url = f'{self.base_url}/beta/private_cellular_networks'

        data = {
            "data": {
                "type": "private_cellular_networks",
                "attributes": {
                    "name": name,
                    "core_ip": core_ip,
                    "ha_enabled": ha_enabled,
                    "mobility_gateway_virtual_ip": mobility_gateway_virtual_ip
                }
            }
        }

        if mobility_gateways:
            relationships = {
                "mobility_gateways": {
                    "data": []
                }
            }
            gateways = mobility_gateways.split(",")

            for gateway in gateways:
                relationships['mobility_gateways']['data'].append({"type": "private_cellular_cores", "id": gateway})

            data['data']['relationships'] = relationships

        ncm = self.session.post(post_url, data=json.dumps(data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def delete_private_cellular_network(self, id):
        """
        Returns information about a private cellular network.
        :param id: ID of the private_cellular_networks record
        :type id: str
        :return: None unless error.
        """
        # TODO support deletion by network name
        call_type = 'Private Cellular Network'
        delete_url = f'{self.base_url}/beta/private_cellular_networks/{id}'

        ncm = self.session.delete(delete_url)
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def get_private_cellular_cores(self, **kwargs):
        """
        Returns information about a private cellular core.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of Mobility Gateways with details.
        """
        call_type = 'Private Cellular Cores'
        get_url = f'{self.base_url}/beta/private_cellular_cores'

        allowed_params = ['created_at',
                          'id',
                          'management_ip',
                          'network',
                          'router',
                          'status',
                          'type',
                          'updated_at',
                          'url',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_private_cellular_core(self, core_id, **kwargs):
        """
        Returns information about a private cellular core.
        :param core_id: ID of the private_cellular_cores record
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: An individual Mobility Gateway with details.
        """
        call_type = 'Private Cellular Core'
        get_url = f'{self.base_url}/beta/private_cellular_cores/{core_id}'

        allowed_params = ['created_at',
                          'id',
                          'management_ip',
                          'network',
                          'router',
                          'status',
                          'type',
                          'updated_at',
                          'url',
                          'fields',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_private_cellular_radios(self, **kwargs):
        """
        Returns information about a private cellular radio.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of Cellular APs with details.
        """
        call_type = 'Private Cellular Radios'
        get_url = f'{self.base_url}/beta/private_cellular_radios'

        allowed_params = ['admin_state',
                          'antenna_azimuth',
                          'antenna_beamwidth',
                          'antenna_downtilt',
                          'antenna_gain',
                          'bandwidth',
                          'category',
                          'cpi_id',
                          'cpi_name',
                          'cpi_signature',
                          'created_at',
                          'description',
                          'fccid',
                          'height',
                          'height_type',
                          'id',
                          'indoor_deployment',
                          'latitude',
                          'location',
                          'longitude',
                          'mac',
                          'name',
                          'network',
                          'serial_number',
                          'tdd_mode',
                          'tx_power',
                          'type',
                          'updated_at',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_private_cellular_radio(self, id, **kwargs):
        """
        Returns information about a private cellular radio.
        :param id: ID of the private_cellular_radios record
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: An individual Cellular AP with details.
        """
        call_type = 'Private Cellular Radios'
        get_url = f'{self.base_url}/beta/private_cellular_radios/{id}'

        allowed_params = ['admin_state',
                          'antenna_azimuth',
                          'antenna_beamwidth',
                          'antenna_downtilt',
                          'antenna_gain',
                          'bandwidth',
                          'category',
                          'cpi_id',
                          'cpi_name',
                          'cpi_signature',
                          'created_at',
                          'description',
                          'fccid',
                          'height',
                          'height_type',
                          'id',
                          'indoor_deployment',
                          'latitude',
                          'location',
                          'longitude',
                          'mac',
                          'name',
                          'network',
                          'serial_number',
                          'tdd_mode',
                          'tx_power',
                          'type',
                          'updated_at',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def update_private_cellular_radio(self, id=None, name=None, **kwargs):
        """
        Updates a Cellular AP's data.
        :param id: ID of the private_cellular_radio record. Must specify this or name.
        :type id: str
        :param name: Name of the Cellular AP. Must specify this or id.
        type id: str
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: Update Cellular AP results.
        """
        call_type = 'Private Cellular Radio'

        if id:
            radio = self.get_private_cellular_radios(id=id)[0]
        elif name:
            radio = self.get_private_cellular_radios(name=name)[0]
        else:
            return "ERROR: Must specify either ID or name"

        if name:
            kwargs['name'] = name

        put_url = f'{self.base_url}/beta/private_cellular_radios/{radio["id"]}'

        if "network" in kwargs.keys():
            relationships = {
                "network": {
                    "data": {
                        "type": "private_cellular_networks",
                        "id": kwargs['network']
                    }
                }
            }
            kwargs.pop("network")

            radio['data']['relationships'] = relationships

        if "location" in kwargs.keys():
            location = {
                "data": {
                    "type": "private_cellular_radio_groups",
                    "id": kwargs['location']
                }
            }
            kwargs.pop("location")
            radio['data']['location'] = location

        allowed_params = ['admin_state',
                          'antenna_azimuth',
                          'antenna_beamwidth',
                          'antenna_downtilt',
                          'antenna_gain',
                          'bandwidth',
                          'category',
                          'cpi_id',
                          'cpi_name',
                          'cpi_signature',
                          'created_at',
                          'description',
                          'fccid',
                          'height',
                          'height_type',
                          'id',
                          'indoor_deployment',
                          'latitude',
                          'location',
                          'longitude',
                          'mac',
                          'name',
                          'network',
                          'serial_number',
                          'tdd_mode',
                          'tx_power']
        params = self.__parse_put_kwargs(kwargs, allowed_params)

        for k, v in params.items():
            radio['attributes'][k] = v

        radio = {"data": radio}

        ncm = self.session.put(put_url, data=json.dumps(radio))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def get_private_cellular_radio_groups(self, **kwargs):
        """
        Returns information about a private cellular core.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of Cellular AP Groups with details.
        """
        call_type = 'Private Cellular Radio Groups'
        get_url = f'{self.base_url}/beta/private_cellular_radio_groups'

        allowed_params = ['created_at',
                          'created_at__lt',
                          'created_at__lte',
                          'created_at__gt',
                          'created_at__gte',
                          'created_at__ne',
                          'description',
                          'id',
                          'name',
                          'network',
                          'type',
                          'updated_at',
                          'updated_at__lt',
                          'updated_at__lte',
                          'updated_at__gt',
                          'updated_at__gte',
                          'updated_at__ne',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_private_cellular_radio_group(self, group_id, **kwargs):
        """
        Returns information about a private cellular core.
        :param group_id: ID of the private_cellular_radio_groups record
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: An individual Cellular AP Group with details.
        """
        call_type = 'Private Cellular Radio Group'
        get_url = f'{self.base_url}/beta/private_cellular_radio_groups/{group_id}'

        allowed_params = ['created_at',
                          'description',
                          'id',
                          'name',
                          'network',
                          'type',
                          'updated_at',
                          'fields',
                          'limit',
                          'sort']
        if "search" not in kwargs.keys():
            params = self.__parse_kwargs(kwargs, allowed_params)
        else:
            if kwargs['search']:
                params = self.__parse_search_kwargs(kwargs, allowed_params)
            else:
                params = self.__parse_kwargs(kwargs, allowed_params)

        results = self.__get_json(get_url, call_type, params=params)
        return results

    def update_private_cellular_radio_group(self, id=None, name=None, **kwargs):
        """
        Updates a Radio Group.
        :param id: ID of the private_cellular_radio_groups record. Must specify this or name.
        :type id: str
        :param name: Name of the Radio Group. Must specify this or id.
        type name: str
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: Update Cellular AP Group results.
        """
        call_type = 'Private Cellular Radio Group'

        if id:
            group = self.get_private_cellular_radio_groups(id=id)[0]
        elif name:
            group = self.get_private_cellular_radio_groups(name=name)[0]
        else:
            return "ERROR: Must specify either ID or name"

        if name:
            kwargs['name'] = name

        put_url = f'{self.base_url}/beta/private_cellular_sims/{group["id"]}'

        if "network" in kwargs.keys():
            relationships = {
                "network": {
                    "data": {
                        "type": "private_cellular_networks",
                        "id": kwargs['network']
                    }
                }
            }
            kwargs.pop("network")

            group['data']['relationships'] = relationships

        allowed_params = ['name',
                          'description']
        params = self.__parse_put_kwargs(kwargs, allowed_params)

        for k, v in params.items():
            group['attributes'][k] = v

        group = {"data": group}

        ncm = self.session.put(put_url, data=json.dumps(group))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def create_private_cellular_radio_group(self, name, description, network=None):
        """
        Creates a Radio Group.
        :param name: Name of the Radio Group.
        type name: str
        :param description: Description of the Radio Group.
        :type description: str
        param network: ID of the private_cellular_network to belong to. Optional.
        :type network: str
        :return: Create Private Cellular Radio Group results.
        """
        call_type = 'Private Cellular Radio Group'

        post_url = f'{self.base_url}/beta/private_cellular_radio_groups'

        group = {
            "data": {
                "type": "private_cellular_radio_groups",
                "attributes": {
                    "name": name,
                    "description": description
                }
            }
        }

        if network:
            relationships = {
                "network": {
                    "data": {
                        "type": "private_cellular_networks",
                        "id": network
                    }
                }
            }

            group['data']['relationships'] = relationships

        ncm = self.session.post(post_url, data=json.dumps(group))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def delete_private_cellular_radio_group(self, id):
        """
        Deletes a private_cellular_radio_group record.
        :param id: ID of the private_cellular_radio_group record
        :type id: str
        :return: None unless error.
        """
        #TODO support deletion by group name
        call_type = 'Private Cellular Radio Group'
        delete_url = f'{self.base_url}/beta/private_cellular_radio_group/{id}'

        ncm = self.session.delete(delete_url)
        result = self._return_handler(ncm.status_code, ncm.text, call_type)
        return result

    def get_private_cellular_sims(self, **kwargs):
        """
        Returns information about a private cellular core.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of PCN SIMs with details.
        """
        call_type = 'Private Cellular SIMs'
        get_url = f'{self.base_url}/beta/private_cellular_sims'

        allowed_params = ['created_at',
                          'created_at__lt',
                          'created_at__lte',
                          'created_at__gt',
                          'created_at__gte',
                          'created_at__ne',
                          'iccid',
                          'id',
                          'imsi',
                          'last_contact_at',
                          'last_contact_at__lt',
                          'last_contact_at__lte',
                          'last_contact_at__gt',
                          'last_contact_at__gte',
                          'last_contact_at__ne',
                          'name',
                          'network',
                          'state',
                          'state_updated_at',
                          'state_updated_at__lt',
                          'state_updated_at__lte',
                          'state_updated_at__gt',
                          'state_updated_at__gte',
                          'state_updated_at__ne',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_private_cellular_sim(self, id, **kwargs):
        """
        Returns information about a private cellular core.
        :param sim_id: ID of the private_cellular_sims record
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: An individual PCN SIM with details.
        """
        call_type = 'Private Cellular SIMs'
        get_url = f'{self.base_url}/beta/private_cellular_sims/{id}'

        allowed_params = ['created_at',
                          'iccid',
                          'id',
                          'imsi',
                          'last_contact_at',
                          'name',
                          'network',
                          'state',
                          'state_updated_at',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def update_private_cellular_sim(self, id=None, iccid=None, imsi=None, **kwargs):
        """
        Updates a SIM's data.
        :param id: ID of the private_cellular_sim record. Must specify ID, ICCID, or IMSI.
        :type id: str
        :param iccid: ICCID. Must specify ID, ICCID, or IMSI.
        :type id: str
        :param imsi: IMSI. Must specify ID, ICCID, or IMSI.
        :type id: str
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: Update PCN SIM results.
        """
        call_type = 'Private Cellular SIM'

        if id:
            sim = self.get_private_cellular_sims(id=id)[0]
        elif iccid:
            sim = self.get_private_cellular_sims(iccid=iccid)[0]
        elif imsi:
            sim = self.get_private_cellular_sims(imsi=imsi)[0]
        else:
            return "ERROR: Must specify either ID, ICCID, or IMSI"

        put_url = f'{self.base_url}/beta/private_cellular_sims/{sim["id"]}'

        if "network" in kwargs.keys():
            relationships = {
                "network": {
                    "data": {
                        "type": "private_cellular_networks",
                        "id": kwargs['network']
                    }
                }
            }
            kwargs.pop("network")

            sim['data']['relationships'] = relationships

        allowed_params = ['name',
                          'state']
        params = self.__parse_put_kwargs(kwargs, allowed_params)

        for k, v in params.items():
            sim['attributes'][k] = v

        sim = {"data": sim}

        ncm = self.session.put(put_url, data=json.dumps(sim))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        return result

    def get_private_cellular_radio_statuses(self, **kwargs):
        """
        Returns information about a private cellular core.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: Cellular radio status for all cellular radios.
        """
        call_type = 'Private Cellular Radio Statuses'
        get_url = f'{self.base_url}/beta/private_cellular_radio_statuses'

        allowed_params = ['admin_state',
                          'boot_time',
                          'cbrs_sas_status',
                          'cell',
                          'connected_ues',
                          'ethernet_status',
                          'id',
                          'ipsec_status',
                          'ipv4_address',
                          'last_update_time',
                          'online_status',
                          'operational_status',
                          'operating_tx_power',
                          's1_status',
                          'time_synchronization',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_private_cellular_radio_status(self, status_id, **kwargs):
        """
        Returns information about a private cellular core.
        :param status_id: ID of the private_cellular_radio_statuses resource
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: Cellular radio status for an individual radio.
        """
        call_type = 'Private Cellular Radio Status'
        get_url = f'{self.base_url}/beta/private_cellular_radio_statuses/{status_id}'

        allowed_params = ['admin_state',
                          'boot_time',
                          'cbrs_sas_status',
                          'cell',
                          'connected_ues',
                          'ethernet_status',
                          'id',
                          'ipsec_status',
                          'ipv4_address',
                          'last_update_time',
                          'online_status',
                          'operational_status',
                          'operating_tx_power',
                          's1_status',
                          'time_synchronization',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)


    def get_public_sim_mgmt_assets(self, **kwargs):
        """
        Returns information about SIM asset resources in your NetCloud Manager account.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: SIM asset resources.
        """
        call_type = 'Private Cellular Radio Status'
        get_url = f'{self.base_url}/beta/public_sim_mgmt_assets'

        allowed_params = ['assigned_imei',
                          'carrier',
                          'detected_imei',
                          'device_status',
                          'iccid',
                          'is_licensed'
                          'type',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_public_sim_mgmt_rate_plans(self, **kwargs):
        """
        Returns information about rate plan resources associated with the SIM assets in your NetCloud Manager account.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: Rate plans for SIM assets.
        """
        call_type = 'Private Cellular Radio Status'
        get_url = f'{self.base_url}/beta/public_sim_mgmt_assets'

        allowed_params = ['carrier',
                          'name',
                          'status',
                          'fields',
                          'limit',
                          'sort']

        params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_exchange_sites(self, site_id: str = None, exchange_network_id: str = None, name: str = None, **kwargs) -> list:
        """
        Returns information about exchange sites.
        
        :param site_id: ID of a specific exchange site to retrieve. Optional.
        :type site_id: str
        :param exchange_network_id: ID of the exchange network to filter sites by. Optional.
        :type exchange_network_id: str
        :param name: Name of the site to filter by. Optional.
        :type name: str
        :param kwargs: Optional parameters such as limit, sort, fields.
            - limit: Maximum number of sites to return.
            - sort: Field to sort the results by. Can be prefixed with '-' for descending order.
            Valid sort fields: name, updated_at
            - fields: List of fields to include in the response.
            Valid fields: name, created_at, updated_at, editable, lan_as_dns, 
                            local_domain, primary_dns, secondary_dns, tags
        :return: A list of exchange sites, a single site if site_id is provided, or an error message if no sites are found.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If an invalid parameter or value is provided.
        """
        call_type = 'Exchange Sites'
        get_url = f'{self.base_url}/beta/exchange_sites'

        allowed_params = {
            'limit': int,
            'sort': str,
            'fields': list
        }

        valid_sort_fields = ['name', 'updated_at']
        valid_fields = ['name', 'created_at', 'updated_at', 'editable', 'lan_as_dns', 
                        'local_domain', 'primary_dns', 'secondary_dns', 'tags']

        params = {}

        if exchange_network_id:
            if not isinstance(exchange_network_id, str):
                raise TypeError("exchange_network_id must be a string")
            params['filter[exchange_network]'] = exchange_network_id

        if name:
            if not isinstance(name, str):
                raise TypeError("name must be a string")
            params['filter[name]'] = name

        # Type checking and validation for parameters
        for key, value in kwargs.items():
            if key in allowed_params:
                if not isinstance(value, allowed_params[key]):
                    raise TypeError(f"{key} must be of type {allowed_params[key].__name__}")
                
                if key == 'sort':
                    sort_field = value.lstrip('-')
                    if sort_field not in valid_sort_fields:
                        raise ValueError(f"Invalid sort field: {sort_field}")
                
                elif key == 'fields':
                    for field in value:
                        if field not in valid_fields:
                            raise ValueError(f"Invalid field: {field}")
                    params[key] = ','.join(value)
                else:
                    params[key] = value
            
            elif key not in ['search', 'filter']:
                raise ValueError(f"Invalid parameter: {key}")

        if site_id:
            if not isinstance(site_id, str):
                raise TypeError("site_id must be a string")
            get_url += f'/{site_id}'
            response = self.__get_json(get_url, call_type)
            
            if response.startswith('ERROR'):
                return [f"No site found with site_id: {site_id}"]
            return response

        params.update(self.__parse_kwargs(kwargs, allowed_params.keys()))
        
        response = self.__get_json(get_url, call_type, params=params)

        if not response:
            if name:
                return [f"No site found with name: {name}"]
            if exchange_network_id:
                return [f"No sites found for exchange_network_id: {exchange_network_id}"]
            
        return response
    
    def create_exchange_site(self, name: str, exchange_network_id: str, router_id: str, **kwargs) -> dict:
        """
        Creates an exchange site.

        :param name: Name of the exchange site.
        :type name: str
        :param exchange_network_id: ID of the exchange network.
        :type exchange_network_id: str
        :param router_id: ID of the endpoint.
        :type router_id: str
        :param kwargs: Optional parameters such as primary_dns, secondary_dns, lan_as_dns, local_domain, tags.
            - primary_dns: Primary DNS of the exchange site.
            - secondary_dns: Secondary DNS of the exchange site.
            - lan_as_dns: Whether LAN is used as DNS. Defaults to False.
            - local_domain: Local domain of the exchange site.
            - tags: List of tags for the exchange site.
        :return: The created exchange site data if successful, error message otherwise.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If required parameters are missing or if an invalid parameter or value is provided.
        """
        call_type = 'Create Exchange Site'

        # Type checking for required parameters
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        if not isinstance(exchange_network_id, str):
            raise TypeError("exchange_network_id must be a string")
        if not isinstance(router_id, str):
            raise TypeError("router_id must be a string")

        post_url = f'{self.base_url}/beta/exchange_sites'

        allowed_params = {
            'primary_dns': str,
            'secondary_dns': str,
            'lan_as_dns': bool,
            'local_domain': str,
            'tags': list
        }

        attributes = {
            'name': name,
            'lan_as_dns': False  # Default value
        }

        # Process optional parameters
        for key, value in kwargs.items():
            if key in allowed_params:
                if not isinstance(value, allowed_params[key]):
                    raise TypeError(f"{key} must be of type {allowed_params[key].__name__}")
                if key == 'tags':
                    if not all(isinstance(tag, str) for tag in value):
                        raise TypeError("All tags must be strings")
                attributes[key] = value
            else:
                raise ValueError(f"Invalid parameter: {key}")

        # Check if lan_as_dns is True and primary_dns is provided
        if attributes.get('lan_as_dns', False) and 'primary_dns' not in attributes:
            raise ValueError("primary_dns is required when lan_as_dns is True")

        data = {
            "data": {
                "type": "exchange_user_managed_sites",
                "attributes": attributes,
                "relationships": {
                    "exchange_network": {
                        "data": {
                            "id": exchange_network_id,
                            "type": "exchange_networks"
                        }
                    },
                    "endpoints": {
                        "data": [
                            {
                                "id": router_id,
                                "type": "endpoints"
                            }
                        ]
                    }
                }
            }
        }

        ncm = self.session.post(post_url, data=json.dumps(data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        if ncm.status_code == 201:
            return ncm.json()['data']
        else:
            return result
        
    def update_exchange_site(self, site_id: str = None, name: str = None, **kwargs) -> dict:
        """
        Updates an exchange site.

        :param site_id: ID of the exchange site to update. Optional if name is provided.
        :type site_id: str, optional
        :param name: Name of the exchange site to update or the new name if site_id is provided.
        :type name: str, optional
        :param kwargs: Optional parameters to update. Can include:
            - primary_dns: New primary DNS for the exchange site.
            - secondary_dns: New secondary DNS for the exchange site.
            - lan_as_dns: Whether LAN should be used as DNS.
            - local_domain: New local domain for the exchange site.
            - tags: New list of tags for the exchange site.
        :return: The updated exchange site data if successful, error message otherwise.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If neither site_id nor name is provided, or if an invalid parameter is provided.
        :raises LookupError: If no site is found when searching by id or name.
        """
        call_type = 'Update Exchange Site'

        if (site_id is None or site_id == '') and (name is None or name == ''):
            raise ValueError("Either site_id or name must be provided and cannot be blank")

        allowed_params = {
            'primary_dns': str,
            'secondary_dns': str,
            'lan_as_dns': bool,
            'local_domain': str,
            'tags': list
        }

        # Get current site data 
        if site_id:
            if not isinstance(site_id, str):
                raise TypeError("site_id must be a string")
            current_site = self.get_exchange_sites(site_id=site_id)
            if not current_site:
                raise LookupError(f"No site found with id: {site_id}")
            current_site = current_site[0]
            update_name = name is not None
        elif name:
            if not isinstance(name, str):
                raise TypeError("name must be a string")
            current_site = self.get_exchange_sites(name=name)
            if not current_site:
                raise LookupError(f"No site found with name: {name}")
            current_site = current_site[0]
            site_id = current_site['id']
            update_name = False

        put_url = f'{self.base_url}/beta/exchange_sites/{site_id}'

        attributes = current_site['attributes']
        exchange_network_id = current_site['relationships']['exchange_network']['data']['id']
        router_id = current_site['relationships']['endpoints']['data'][0]['id']

        # Update name if site_id was provided and name is different
        if update_name and name != attributes['name']:
            attributes['name'] = name

        # Update attributes with new values
        for key, expected_type in allowed_params.items():
            if key in kwargs:
                value = kwargs[key]
                if key == 'tags':
                    if not isinstance(value, list):
                        raise TypeError("tags must be a list")
                    if not all(isinstance(tag, str) for tag in value):
                        raise TypeError("All tags must be strings")
                elif not isinstance(value, expected_type):
                    raise TypeError(f"{key} must be of type {expected_type.__name__}")
                attributes[key] = value

        # Check if lan_as_dns is True and primary_dns is provided
        if attributes.get('lan_as_dns', False) and 'primary_dns' not in attributes:
            raise ValueError("primary_dns is required when lan_as_dns is True")

        data = {
            "data": {
                "type": "exchange_user_managed_sites",
                "id": site_id,
                "attributes": attributes,
                "relationships": {
                    "exchange_network": {
                        "data": {
                            "type": "exchange_networks",
                            "id": exchange_network_id
                        }
                    },
                    "endpoints": {
                        "data": [{
                            "type": "routers",
                            "id": router_id
                        }]
                    }
                }
            }
        }

        ncm = self.session.put(put_url, data=json.dumps(data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        if ncm.status_code == 200:
            return ncm.json()['data']
        else:
            return result
    
    def delete_exchange_site(self, site_id: str = None, site_name: str = None) -> dict:
        """
        Deletes an exchange site and its associated resources.

        :param site_id: ID of the exchange site to delete. Optional if site_name is provided.
        :type site_id: str, optional
        :param site_name: Name of the exchange site to delete. Optional if site_id is provided.
        :type site_name: str, optional
        :return: The response from the DELETE request.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If neither site_id nor site_name is provided.
        """
        call_type = 'Delete Exchange Site'

        if not site_id and not site_name:
            raise ValueError("Either site_id or site_name must be provided")

        if site_name and not isinstance(site_name, str):
            raise TypeError("site_name must be a string")
        if site_id and not isinstance(site_id, str):
            raise TypeError("site_id must be a string")

        # Delete associated resources
        if site_id:
            resource_deletion_results = self.delete_exchange_resource(site_id=site_id)
        else:
            resource_deletion_results = self.delete_exchange_resource(site_name=site_name)

        # Delete the exchange site
        if site_id:
            delete_url = f'{self.base_url}/beta/exchange_sites/{site_id}'
        else:
            site_id = self.get_exchange_sites(name=site_name)[0]["id"]
            delete_url = f'{self.base_url}/beta/exchange_sites/{site_id}'

        ncm = self.session.delete(delete_url)
        
        if ncm.status_code == 204:
            site_deletion_result = "deleted"
        else:
            site_deletion_result = "error"

        return {
            "site_deletion_result": site_deletion_result,
            "resource_deletion_results": resource_deletion_results
        }
    
    def get_exchange_resources(self, site_id: str = None, exchange_network_id: str = None, resource_id: str = None, site_name: str = None, **kwargs) -> list:
        """
        Returns information about exchange resources.
        
        :param site_id: ID of the exchange site to filter resources by. Optional.
        :type site_id: str
        :param exchange_network_id: ID of the exchange network to filter resources by. Optional.
        :type exchange_network_id: str
        :param resource_id: ID of a specific exchange resource to retrieve. Optional.
        :type resource_id: str
        :param site_name: Name of the exchange site to filter resources by. Optional.
        :type site_name: str
        :param kwargs: Optional parameters such as name, limit, sort, fields, resource_type.
            - name: Name of the resource to filter by.
            - limit: Maximum number of resources to return.
            - sort: Field to sort the results by. Can be prefixed with '-' for descending order.
            - fields: List of fields to include in the response.
            - resource_type: Type of resource to filter by (exchange_fqdn_resources, exchange_wildcard_fqdn_resources, or exchange_ipsubnet_resources).
        :return: A list of exchange resources or a single resource if resource_id is provided.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If an invalid parameter or value is provided.
        :raises LookupError: If no site is found when searching by site_name.
        """
        call_type = 'Exchange Resources'

        if resource_id:
            if not isinstance(resource_id, str):
                raise TypeError("resource_id must be a string")
            get_url = f"{self.base_url}/beta/exchange_resources/{resource_id}"
        else:
            get_url = f"{self.base_url}/beta/exchange_resources"

        params = {}
        if site_name:
            if not isinstance(site_name, str):
                raise TypeError("site_name must be a string")
            sites = self.get_exchange_sites(name=site_name)
            if not sites:
                raise LookupError(f"No site found with name: {site_name}")
            site_id = sites[0]['id']

        if site_id:
            if not isinstance(site_id, str):
                raise TypeError("site_id must be a string")
            params['filter[exchange_site]'] = site_id
        elif exchange_network_id:
            if not isinstance(exchange_network_id, str):
                raise TypeError("exchange_network_id must be a string")
            params['filter[exchange_network]'] = exchange_network_id

        allowed_params = {
            'name': str,
            'limit': int,
            'sort': str,
            'fields': list,
            'resource_type': str
        }

        valid_sort_fields = ['name', 'created_at', 'updated_at', 'protocols', 'tags', 'domain', 'ip', 'static_prime_ip', 'port_ranges']
        valid_fields = ['name', 'created_at', 'updated_at', 'protocols', 'tags', 'domain', 'ip', 'static_prime_ip', 'port_ranges']
        valid_types = ['exchange_fqdn_resources', 'exchange_wildcard_fqdn_resources', 'exchange_ipsubnet_resources']

        for key, value in kwargs.items():
            if key in allowed_params:
                if not isinstance(value, allowed_params[key]):
                    raise TypeError(f"{key} must be of type {allowed_params[key].__name__}")
                
                if key == 'sort':
                    if value.lstrip('-') not in valid_sort_fields:
                        raise ValueError(f"Invalid sort field: {value}")
                
                elif key == 'fields':
                    for field in value:
                        if field not in valid_fields:
                            raise ValueError(f"Invalid field: {field}")
                    params[key] = ','.join(value)
                
                elif key == 'resource_type':
                    if value not in valid_types:
                        raise ValueError(f"Invalid resource type: {value}. Valid types are: {', '.join(valid_types)}")
                    params['filter[type]'] = value
                
                else:
                    params[key] = value
            
            elif key not in ['search', 'filter']:
                raise ValueError(f"Invalid parameter: {key}")
            else:
                params[key] = value

        response = self.session.get(get_url, params=params)

        if response.status_code == 200:
            data = response.json()['data']
            return data if isinstance(data, list) else [data]
        else:
            return f"ERROR: {response.status_code}: {response.text}"
        
    def create_exchange_resource(self, resource_name: str, resource_type: str, site_id: str = None, site_name: str = None, **kwargs) -> dict:
        """
        Creates an exchange resource.

        :param resource_name: Name for the new resource.
        :type resource_name: str
        :param resource_type: Type of resource to create. Must be one of:
            'exchange_fqdn_resources', 'exchange_wildcard_fqdn_resources', or 'exchange_ipsubnet_resources'.
        :type resource_type: str
        :param site_id: NCX Site ID to add the resource to. Optional if site_name is provided.
        :type site_id: str
        :param site_name: Name of the NCX Site to add the resource to. Optional if site_id is provided.
        :type site_name: str
        :param kwargs: Optional parameters for the resource. Can include:
            - protocols: List of protocols (e.g., ['TCP'], ['UDP'], ['TCP', 'UDP'], or ['ICMP']).
            - tags: List of tags for the resource.
            - domain: Domain name for FQDN or wildcard FQDN resources. Required for these types.
              For wildcard FQDN, must start with '*.'.
            - ip: IP address for IP subnet resources. Required for this type.
            - static_prime_ip: Static prime IP for the resource.
            - port_ranges: List of port ranges. Each range can be an int, a string (e.g., '80' or '8000-8080').
              Will be converted to a list of dicts with 'lower_limit' and 'upper_limit'.
              Not allowed when protocol is ICMP or None.
        :return: The created exchange resource data if successful, error message otherwise.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If required parameters are missing, if an invalid resource type is provided,
                            if an invalid parameter or value is provided, or if port ranges are provided
                            with ICMP protocol or no protocol.
        :raises LookupError: If no site is found when searching by site_name.
        """
        call_type = 'Create Exchange Site Resource'

        # Type checking for required parameters
        if not isinstance(resource_name, str):
            raise TypeError("resource_name must be a string")
        if not isinstance(resource_type, str):
            raise TypeError("resource_type must be a string")

        # Validate and get site_id
        if site_id is None and site_name is None:
            raise ValueError("Either site_id or site_name must be provided")
        
        if site_name:
            if not isinstance(site_name, str):
                raise TypeError("site_name must be a string")
            sites = self.get_exchange_sites(name=site_name)
            if not sites:
                raise LookupError(f"No site found with name: {site_name}")
            site_id = sites[0]['id']
        elif not isinstance(site_id, str):
            raise TypeError("site_id must be a string")

        valid_resource_types = ['exchange_fqdn_resources', 'exchange_wildcard_fqdn_resources', 'exchange_ipsubnet_resources', 'exchange_http_resources', 'exchange_https_resources']
        if resource_type not in valid_resource_types:
            raise ValueError(f"Invalid resource_type. Must be one of: {', '.join(valid_resource_types)}")

        post_url = f'{self.base_url}/beta/exchange_resources'

        allowed_params = {
            'protocols': (list, type(None)),
            'tags': list,
            'domain': str,
            'ip': str,
            'static_prime_ip': str,
            'port_ranges': (list, type(None))
        }

        attributes = {'name': resource_name}

        # Validate required parameters based on resource_type
        if resource_type == 'exchange_ipsubnet_resources':
            if 'ip' not in kwargs:
                raise ValueError("'ip' is required for IP subnet resources")
            attributes['ip'] = kwargs['ip']
        elif resource_type in ['exchange_fqdn_resources', 'exchange_wildcard_fqdn_resources']:
            if 'domain' not in kwargs:
                raise ValueError("'domain' is required for FQDN and wildcard FQDN resources")
            domain = kwargs['domain']
            if resource_type == 'exchange_wildcard_fqdn_resources' and not domain.startswith('*.'):
                raise ValueError("Domain for wildcard FQDN resources must start with '*.'")
            attributes['domain'] = domain

        # Process optional parameters
        for key, value in kwargs.items():
            if key in allowed_params and key not in attributes:
                if not isinstance(value, allowed_params[key]):
                    raise TypeError(f"{key} must be of type {allowed_params[key].__name__}")
                if key == 'tags':
                    if not all(isinstance(tag, str) for tag in value):
                        raise TypeError("All tags must be strings")
                if key == 'protocols':
                    valid_protocols = [['TCP'], ['UDP'], ['TCP', 'UDP'], ['ICMP'], None]
                    if value not in valid_protocols:
                        raise ValueError(f"Invalid protocols. Must be one of: {valid_protocols}")
                    attributes[key] = value
                if key == 'port_ranges':
                    # Check if protocols are set and not ICMP or None
                    if 'protocols' not in attributes or attributes['protocols'] in [['ICMP'], None]:
                        raise ValueError("Port ranges cannot be specified when protocol is ICMP or None")
                    
                    parsed_ranges = []
                    for range_str in value:
                        if isinstance(range_str, int):
                            parsed_ranges.append({'lower_limit': range_str, 'upper_limit': range_str})
                        elif isinstance(range_str, str):
                            if '-' in range_str:
                                lower, upper = map(int, range_str.split('-'))
                                if lower > upper:
                                    raise ValueError(f"Invalid port range: {range_str}. Lower limit must be less than or equal to upper limit.")
                                parsed_ranges.append({'lower_limit': lower, 'upper_limit': upper})
                            else:
                                port = int(range_str)
                                parsed_ranges.append({'lower_limit': port, 'upper_limit': port})
                        else:
                            raise ValueError(f"Invalid port range format: {range_str}")
                    attributes[key] = parsed_ranges
                else:
                    attributes[key] = value

        data = {
            "data": {
                "type": resource_type,
                "attributes": attributes,
                "relationships": {
                    "exchange_site": {
                        "data": {
                            "id": site_id,
                            "type": "exchange_sites"
                        }
                    }
                }
            }
        }

        ncm = self.session.post(post_url, data=json.dumps(data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        if ncm.status_code == 201:
            return ncm.json()['data']
        else:
            return result
    
    def update_exchange_resource(self, resource_id: str, **kwargs) -> dict: #site_id: str = None, site_name: str = None,
        """
        Updates an exchange resource.

        :param resource_id: ID of the exchange resource to update.
        :type resource_id: str
        :param site_id: NCX Site ID of the resource. Optional if site_name is provided.
        :type site_id: str
        :param site_name: Name of the NCX Site of the resource. Optional if site_id is provided.
        :type site_name: str
        :param kwargs: Optional parameters to update. Can include:
            - name: New name for the resource.
            - protocols: List of protocols (e.g., ['TCP'], ['UDP'], ['TCP', 'UDP'], or ['ICMP']).
            - tags: List of tags for the resource.
            - domain: Domain name for FQDN or wildcard FQDN resources.
            - ip: IP address for IP subnet resources.
            - static_prime_ip: Static prime IP for the resource.
            - port_ranges: List of port ranges. Each range can be an int, a string (e.g., '80' or '8000-8080').
              Will be converted to a list of dicts with 'lower_limit' and 'upper_limit'.
              Not allowed when protocol is ICMP or None.
        :return: The updated exchange resource data if successful, error message otherwise.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If an invalid parameter or value is provided,
                            or if port ranges are provided with ICMP protocol or no protocol.
        :raises LookupError: If no site is found when searching by site_name.
        """
        call_type = 'Update Exchange Resource'

        if not isinstance(resource_id, str):
            raise TypeError("resource_id must be a string")

        # Raise an error if resource_type is provided
        if 'resource_type' in kwargs:
            raise ValueError("resource_type cannot be updated after resource creation")

        # Get current resource data
        current_resource = self.get_exchange_resources(resource_id=resource_id)[0]
        resource_type = current_resource['type']
        site_id = current_resource['relationships']['exchange_site']['data']['id']

        put_url = f'{self.base_url}/beta/exchange_resources/{resource_id}'

        allowed_params = {
            'name': str,
            'protocols': (list, type(None)),
            'tags': list,
            'domain': str,
            'ip': str,
            'static_prime_ip': str,
            'port_ranges': (list, type(None))
        }

        attributes = current_resource['attributes']

        # Process optional parameters
        for key, value in kwargs.items():
            if key in allowed_params:
                if not isinstance(value, allowed_params[key]):
                    raise TypeError(f"{key} must be of type {allowed_params[key].__name__}")
                if key == 'tags':
                    if not all(isinstance(tag, str) for tag in value):
                        raise TypeError("All tags must be strings")
                if key == 'protocols':
                    valid_protocols = [['TCP'], ['UDP'], ['TCP', 'UDP'], ['ICMP'], None]
                    if value not in valid_protocols:
                        raise ValueError(f"Invalid protocols. Must be one of: {valid_protocols}")
                    # if protocols is set to ICMP or None, port_ranges must be None
                    if value in [['ICMP'], None]:
                        attributes['port_ranges'] = None
                if key == 'port_ranges':
                    # Check if protocols are set and not ICMP or None
                    if 'protocols' not in attributes or attributes['protocols'] in [['ICMP'], None]:
                        raise ValueError("Port ranges cannot be specified when protocol is ICMP or None")
                    
                    parsed_ranges = []
                    for range_str in value:
                        if isinstance(range_str, int):
                            parsed_ranges.append({'lower_limit': range_str, 'upper_limit': range_str})
                        elif isinstance(range_str, str):
                            if '-' in range_str:
                                lower, upper = map(int, range_str.split('-'))
                                if lower > upper:
                                    raise ValueError(f"Invalid port range: {range_str}. Lower limit must be less than or equal to upper limit.")
                                parsed_ranges.append({'lower_limit': lower, 'upper_limit': upper})
                            else:
                                port = int(range_str)
                                parsed_ranges.append({'lower_limit': port, 'upper_limit': port})
                        else:
                            raise ValueError(f"Invalid port range format: {range_str}")
                    value = parsed_ranges
                attributes[key] = value

        data = {
            "data": {
                "type": resource_type,
                "id": resource_id,
                "attributes": attributes,
                "relationships": {
                    "exchange_site": {
                        "data": {
                            "type": "exchange_sites",
                            "id": site_id
                        }
                    }
                }
            }
        }

        ncm = self.session.put(put_url, data=json.dumps(data))
        result = self._return_handler(ncm.status_code, ncm.json(), call_type)
        if ncm.status_code == 200:
            return ncm.json()['data']
        else:
            return result
        
    def delete_exchange_resource(self, resource_id: str = None, site_name: str = None, site_id: str = None) -> list:
        """
        Deletes exchange resources.

        :param resource_id: ID of the exchange resource to delete. Optional if site_name or site_id is provided.
        :type resource_id: str, optional
        :param site_name: Name of the exchange site to filter resources by. Optional if resource_id or site_id is provided.
        :type site_name: str, optional
        :param site_id: ID of the exchange site to filter resources by. Optional if resource_id or site_name is provided.
        :type site_id: str, optional
        :return: The response from the DELETE request.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If none of resource_id, site_name, or site_id is provided.
        :raises LookupError: If no site is found when searching by site_name.
        """
        call_type = 'Delete Exchange Resource'

        if not resource_id and not site_name and not site_id:
            raise ValueError("Either resource_id, site_name, or site_id must be provided")

        resource_ids = []

        if resource_id:
            if not isinstance(resource_id, str):
                raise TypeError("resource_id must be a string")
            resource_ids.append(resource_id)
        else:
            if site_name:
                if not isinstance(site_name, str):
                    raise TypeError("site_name must be a string")
                sites = self.get_exchange_sites(name=site_name)
                if not sites:
                    raise LookupError(f"No site found with name: {site_name}")
                site_id = sites[0]['id']
            elif site_id and not isinstance(site_id, str):
                raise TypeError("site_id must be a string")

            resources = self.get_exchange_resources(site_id=site_id)
            resource_ids = [resource['id'] for resource in resources]

        results = []
        for rid in resource_ids:
            delete_url = f'{self.base_url}/beta/exchange_resources/{rid}'
            ncm = self.session.delete(delete_url)
            if ncm.status_code == 204:
                results.append({'resource_id': rid, 'status': 'deleted'})
            else:
                results.append({'resource_id': rid, 'status': 'error'})

        return results

    def get_account_authorizations(self, **kwargs):
        """
        Get account authorizations
        
        Args:
            **kwargs: Optional parameters for filtering, sorting, and pagination
                     Supported parameters include:
                     - fields: Comma-separated list of fields to return
                     - user: Filter by user
                     - sort: Field to sort by
                     - limit: Number of records to return
                     - search: Search term to filter results
        
        Returns:
            List of account authorization objects
        """
        get_url = f'{self.base_url}/beta/account_authorizations'
        call_type = 'Account Authorizations'
        allowed_params = ['fields', 'user', 'sort', 'limit']
        params = self.__parse_kwargs(kwargs, allowed_params)
        
        return self.__get_json(get_url, call_type, params=params)

    def put_account_authorizations(self, authorization_id: str, account_authorization: dict):
        """
        Update an account authorization role
        
        Args:
            authorization_id: ID of the authorization to update
            account_authorization: Account authorization object
        
        Returns:
            Server response
        """
        put_url = f'{self.base_url}/beta/account_authorizations/{authorization_id}'
        call_type = 'Account Authorization'
        ncm = self.session.put(put_url, json=account_authorization)
        return self._return_handler(ncm.status_code, ncm.json(), call_type)

    def update_user_role(self, email: str, new_role: str) -> dict:
        """
        Updates the role of a user in NCM.
        
        Args:
            email (str): Email address of the user
            new_role (str): New role to assign to the user
            
        Returns:
            dict: Response from the API containing the updated authorization
        """
        try:
            # Find user
            users = self.get_users(email=email)
            if not users:
                raise ValueError(f"User not found: {email}")
            
            user_id = users[0]['id']

            # Get account authorizations
            auths = self.get_account_authorizations(user=user_id)
            if not auths:
                raise ValueError(f"No account authorization found for: {email}")

            account_auth_data = auths[0]
            account_auth_id = account_auth_data['id']

            # Update authorization
            account_auth = {
                "data": {
                    **account_auth_data,
                    "attributes": {
                        **account_auth_data["attributes"],
                        "role": new_role
                    }
                }
            }
            call_type = 'Update User Role'
            response = self.put_account_authorizations(account_auth_id, account_auth)
            return response
            
        except Exception as e:
            self.log('error', f"Error updating role for {email}: {str(e)}")
            raise
        
'''
    def get_group_modem_upgrade_jobs(self, **kwargs):
        """
        Returns users with details.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of users with details.
        """
        call_type = 'Group Modem Upgrades'
        get_url = f'{self.base_url}/beta/group_modem_upgrade_jobs'

        allowed_params = ['id',
                          'group_id',
                          'module_id',
                          'carrier_id',
                          'overwrite',
                          'active_only',
                          'upgrade_only',
                          'batch_size',
                          'created_at',
                          'created_at__lt',
                          'created_at__lte',
                          'created_at__gt',
                          'created_at__gte',
                          'created_at__ne',
                          'updated_at',
                          'updated_at__lt',
                          'updated_at__lte',
                          'updated_at__gt',
                          'updated_at__gte',
                          'updated_at__ne',
                          'available_version',
                          'modem_count',
                          'success_count',
                          'failed_count',
                          'statuscarrier_name',
                          'module_name',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        if "search" not in kwargs.keys():
            params = self.__parse_kwargs(kwargs, allowed_params)
        else:
            if kwargs['search']:
                params = self.__parse_search_kwargs(kwargs, allowed_params)
            else:
                params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_group_modem_upgrade_job(self, job_id, **kwargs):
        """
        Returns users with details.
        :param job_id: The ID of the job
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of users with details.
        """
        call_type = 'Group Modem Upgrades'
        get_url = f'{self.base_url}/beta/group_modem_upgrade_jobs/{job_id}'

        allowed_params = ['id',
                          'group_id',
                          'module_id',
                          'carrier_id',
                          'overwrite',
                          'active_only',
                          'upgrade_only',
                          'batch_size',
                          'created_at',
                          'updated_at',
                          'available_version',
                          'modem_count',
                          'success_count',
                          'failed_count',
                          'statuscarrier_name',
                          'module_name',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        if "search" not in kwargs.keys():
            params = self.__parse_kwargs(kwargs, allowed_params)
        else:
            if kwargs['search']:
                params = self.__parse_search_kwargs(kwargs, allowed_params)
            else:
                params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_group_modem_upgrade_summary(self, **kwargs):
        """
        Returns users with details.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of users with details.
        """
        call_type = 'Group Modem Upgrades'
        get_url = f'{self.base_url}/beta/group_modem_upgrade_jobs'

        allowed_params = ['group_id',
                          'module_id',
                          'module_name',
                          'upgradable_modems',
                          'up_to_date_modems',
                          'summary_data',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        if "search" not in kwargs.keys():
            params = self.__parse_kwargs(kwargs, allowed_params)
        else:
            if kwargs['search']:
                params = self.__parse_search_kwargs(kwargs, allowed_params)
            else:
                params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)

    def get_group_modem_upgrade_device_summary(self, **kwargs):
        """
        Returns users with details.
        :param kwargs: A set of zero or more allowed parameters
          in the allowed_params list.
        :return: A list of users with details.
        """
        call_type = 'Group Modem Upgrades'
        get_url = f'{self.base_url}/beta/group_modem_upgrade_jobs'

        allowed_params = ['group_id',
                          'module_id',
                          'carrier_id',
                          'overwrite',
                          'active_only',
                          'upgrade_only',
                          'router_name',
                          'net_device_name',
                          'current_version',
                          'type',
                          'fields',
                          'limit',
                          'sort']

        if "search" not in kwargs.keys():
            params = self.__parse_kwargs(kwargs, allowed_params)
        else:
            if kwargs['search']:
                params = self.__parse_search_kwargs(kwargs, allowed_params)
            else:
                params = self.__parse_kwargs(kwargs, allowed_params)
        return self.__get_json(get_url, call_type, params=params)
'''

class NcmClientv2v3:

    def __init__(self, 
              api_keys=None,
              api_key=None,
              log_events=True,
              logger=None,
              retries=5,
              retry_backoff_factor=2,
              retry_on=None,
              base_url=None,
              base_url_v3=None):
        """
        :param api_keys: Dictionary of API credentials (apiv2).
            Optional, but must be set before calling functions.
        :type api_keys: dict
        :param api_key: API key for apiv3.
            Optional, but must be set before calling functions.
        :type api_key: str
        """
        api_keys = api_keys or {}
        apiv3_key = api_keys.pop('token', None) or api_key
        self.v2 = None
        self.v3 = None
        if api_keys:
            self.v2 = NcmClientv2(api_keys=api_keys, 
                                  log_events=log_events,
                                  logger=logger,
                                  retries=retries, 
                                  retry_backoff_factor=retry_backoff_factor, 
                                  retry_on=retry_on, 
                                  base_url=base_url)
        if apiv3_key:
            base_url = base_url_v3 if api_keys else base_url
            self.v3 = NcmClientv3(api_key=apiv3_key, 
                                  log_events=log_events, 
                                  logger=logger,
                                  retries=retries, 
                                  retry_backoff_factor=retry_backoff_factor, 
                                  retry_on=retry_on, 
                                  base_url=base_url)
        
    def __getattribute__(self, name):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            # Prioritize v3 over v2
            if self.v3 and hasattr(self.v3, name):
                return getattr(self.v3, name)
            if self.v2 and hasattr(self.v2, name):
                return getattr(self.v2, name)
            raise


class NcmClient:
    """
    This NCM Client class provides functions for interacting with =
    the Cradlepoint NCM API. Full documentation of the Cradlepoint API can be
    found at: https://developer.cradlepoint.com
    """

    def __new__(cls, api_keys=None, api_key=None, **kwargs):
        api_keys = {**api_keys} or {}
        apiv3_key = api_keys.pop('token', None) or api_key
        v2 = bool(api_keys)
        v3 = bool(apiv3_key)
        if v2 and v3:
            return NcmClientv2v3(api_keys=api_keys, api_key=apiv3_key, **kwargs)
        if v2 or not (v2 or v3):
            return NcmClientv2(api_keys=api_keys, **kwargs)
        else:
            return NcmClientv3(api_key=apiv3_key, **kwargs)
