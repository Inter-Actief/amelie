import json
import re
from typing import Optional, Dict, Tuple, Union

from django.test import Client
from graphene_django.utils.testing import GraphQLTestMixin

from amelie.tools.tests import TestCase


class GraphQLClient(Client):
    """
    Django Test Client with secure=True set for the POST request, to make sure test requests are made
    to the secure port. This is needed because in our settings the SECURE_SSL_REDIRECT setting is set to True.
    """
    def post(self, *args, **kwargs):
        kwargs['secure'] = True
        return super().post(*args, **kwargs)


class BaseGraphQLPrivateFieldTests(GraphQLTestMixin, TestCase):
    MODEL_ERROR_REGEX = re.compile(r".* matching query does not exist\.")
    FIELD_ERROR_REGEX = re.compile(r"Cannot query field '.*' on type '.*'\.")

    def setUp(self):
        super(BaseGraphQLPrivateFieldTests, self).setUp()
        self.client = GraphQLClient()

        # Generate basic data
        self.load_basic_data()

    def _test_private_model(self, query_name: str, public_field_spec: str = "id",
                            variables: Optional[Dict[str, Tuple[Union[str, int], str]]] = None,
                            error_regex: Optional[re.Pattern] = None):
        """
        Test if a model instance that should be private is actually not accessible via GraphQL.

        :param query_name: The GraphQL query name to test. I.E. activity in `query{activity(id: 1){ ... }}`
        :type query_name: str

        :param public_field_spec: Specification of a public field that is queryable on public instances of the model.
                                  This can be a simple name of a field, or a field in some nested object.
                                  For example for activity: "id" or "photos { created }"
        :type public_field_spec: str

        :param variables: A dictionary of variables used in the GraphQL query to select the instance.
                          Key is the variable name, value is a tuple with the value, and the GraphQL type of the var.
                          For example to select an activity by ID: {'id': (1, 'ID')}
                          Or a committee by its slug: {'slug': ('www', 'String')}
        :type variables: Optional[Dict[str, Tuple[str, str]]]

        :param error_regex: A regular expression pattern to match expected query errors to.
        :type error_regex: re.Pattern
        """
        # Use default pattern if not given
        if error_regex is None:
            error_regex = BaseGraphQLPrivateFieldTests.MODEL_ERROR_REGEX

        params = ", ".join(f"{k}: ${k}" for k in variables.keys()) if variables else ""
        param_types = ", ".join(f"${k}: {v[1]}" for k, v in variables.items()) if variables else ""
        param_types = f"({param_types})" if param_types else ""
        query_variables = {x: v[0] for x, v in variables.items()}
        query = f'''
            query {param_types} {{
                {query_name}({params}) {{
                    {public_field_spec}
                }}
            }}
        '''
        response = self.query(query, variables=query_variables)

        self.assertResponseHasErrors(
            response,
            f"Query for '{query_name}', private object '{query_variables}' does not return an error!"
        )
        # Check if the error received has the correct error message format, so we don't
        # accidentally consider a different error as a 'successful' result.
        content = json.loads(response.content)
        for error in content['errors']:
            # If different error than expected, throw error.
            self.assertRegex(
                error['message'], error_regex,
                f"Query for '{query_name}', private object '{query_variables}' raised a different error than expected!\n"
                f"{error['message']}"
            )

    def _test_private_model_list(self, query_name: str, public_field_spec: str = "id",
                                 variables: Optional[Dict[str, Tuple[str, str]]] = None,
                                 error_regex: Optional[re.Pattern] = None):
        """
        Test if a model instance that should be private is not in the list returned by a GraphQL query.

        :param query_name: The GraphQL query name to test. I.E. activity in `query{activity(id: 1){ ... }}`
        :type query_name: str

        :param public_field_spec: Specification of a public field that is queryable on public instances of the model.
                                  This can be a simple name of a field, or a field in some nested object.
                                  For example for activity: "id" or "photos { created }"
        :type public_field_spec: str

        :param variables: A dictionary of variables used in the GraphQL query to select the instance.
                          Key is the variable name, value is a tuple with the value, and the GraphQL type of the var.
                          For example to select an activity by ID: {'id': (1, 'ID')}
                          Or a committee by its slug: {'slug': ('www', 'String')}
        :type variables: Optional[Dict[str, Tuple[str, str]]]

        :param error_regex: A regular expression pattern to match expected query errors to.
        :type error_regex: re.Pattern
        """
        # Use default pattern if not given
        if error_regex is None:
            error_regex = BaseGraphQLPrivateFieldTests.MODEL_ERROR_REGEX

        params = ", ".join(f"{k}: ${k}" for k in variables.keys()) if variables else ""
        param_types = ", ".join(f"${k}: {v[1]}" for k, v in variables.items()) if variables else ""
        param_types = f"({param_types})" if param_types else ""
        query_variables = {x: v[0] for x, v in variables.items()}
        query = f'''
            query {param_types} {{
                {query_name}({params}) {{
                    {public_field_spec}
                }}
            }}
        '''
        response = self.query(query, variables=query_variables)

        # Request should succeed
        self.assertResponseNoErrors(
            response,
            f"Query for '{query_name}', private object '{query_variables}' should succeed but returned an error!"
        )

        # Check if the results list is empty.
        content = json.loads(response.content)
        num_obj = len(content['data'][query_name]['results'])
        self.assertEqual(
            content['data'][query_name]['results'], [],
            f"Query for '{query_name}', private object '{query_variables}' did not return 0 expected objects (returned {num_obj})!"
        )

    def _test_public_model_and_private_field(self, query_name: str, field_name: str, field_spec: str,
                                             variables: Optional[Dict[str, Tuple[str, str]]] = None):
        """
        Test if a field that should be private on a model instance is actually not accessible via GraphQL.

        :param query_name: The GraphQL query name to test. I.E. activity in `query{activity(id: 1){ ... }}`
        :type query_name: str

        :param field_name: User-friendly name of the GraphQL field name being tested. Only used in log messages.
        :type field_name: str

        :param field_spec: Specification of a private field that needs to be tested for privateness.
                                  This can be a simple name of a field, or a field in some nested object.
                                  For example for activity: "id" or "photos { created }"
        :type field_spec: str

        :param variables: A dictionary of variables used in the GraphQL query to select the instance.
                          Key is the variable name, value is a tuple with the value, and the GraphQL type of the var.
                          For example to select an activity by ID: {'id': (1, 'ID')}
                          Or a committee by its slug: {'slug': ('www', 'String')}
        :type variables: Optional[Dict[str, Tuple[str, str]]]
        """
        params = ", ".join(f"{k}: ${k}" for k in variables.keys()) if variables else ""
        param_types = ", ".join(f"${k}: {v[1]}" for k, v in variables.items()) if variables else ""
        param_types = f"({param_types})" if param_types else ""
        query_variables = {x: v[0] for x, v in variables.items()}
        query = f'''
            query {param_types} {{
                {query_name}({params}) {{
                    {field_spec}
                }}
            }}
        '''
        response = self.query(query, variables=query_variables)

        self.assertResponseHasErrors(
            response,
            f"Query for '{query_name}', private field spec '{field_name}' does not return an error!"
        )
        # Check if the error received has the correct error message format, so we don't
        # accidentally consider a different error as a 'successful' result.
        content = json.loads(response.content)
        for error in content['errors']:
            # If different error than expected, throw error.
            self.assertRegex(
                error['message'], BaseGraphQLPrivateFieldTests.FIELD_ERROR_REGEX,
                f"Query for '{query_name}', private field spec '{field_name}' raised a different error than expected!\n"
                f"{error['message']}"
            )
