import datetime
import json
import logging
import os

import azure.functions as func
import pytz
import requests
from azure.cosmosdb.table.tableservice import TableService


def get_graph_api_token():
    oauth2_headers = {"Content-Type": "application/x-www-form-urlencoded"}
    oauth2_body = {
        "client_id": os.environ["GRAPH_CLIENT_ID"],
        "client_secret": os.environ["GRAPH_CLIENT_SECRET"],
        "grant_type": "client_credentials",
        "scope": "https://graph.microsoft.com/.default",
    }
    oauth2_url = (
        f"https://login.microsoftonline.com/{os.environ['TENANT_ID']}/oauth2/v2.0/token"
    )
    try:
        return requests.post(
            url=oauth2_url, headers=oauth2_headers, data=oauth2_body
        ).json()["access_token"]

    except requests.exceptions.RequestException as e:
        raise SystemExit(e)


def get_rest_api_token():
    oauth2_headers = {"Content-Type": "application/x-www-form-urlencoded"}
    oauth2_body = {
        "client_id": os.environ["REST_CLIENT_ID"],
        "client_secret": os.environ["REST_CLIENT_SECRET"],
        "grant_type": "client_credentials",
        "resource": "https://management.azure.com",
    }
    oauth2_url = (
        f"https://login.microsoftonline.com/{os.environ['TENANT_ID']}/oauth2/token"
    )
    try:
        return requests.post(
            url=oauth2_url, headers=oauth2_headers, data=oauth2_body
        ).json()["access_token"]

    except requests.exceptions.RequestException as e:
        raise SystemExit(e)


def get_api_headers(token):
    return {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    }


def get_subscription(id, rest_api_headers):
    try:
        return requests.get(
            url=f"https://management.azure.com/subscriptions/{id}?api-version=2020-01-01",
            headers=rest_api_headers,
        ).json()["displayName"]

    except requests.exceptions.RequestException as e:
        raise SystemExit(e)


def get_upn(id, type, graph_api_headers):
    try:
        return (
            requests.get(
                url=f"https://graph.microsoft.com/v1.0/users/{id}",
                headers=graph_api_headers,
            ).json()["userPrincipalName"]
            if type == "User"
            else requests.get(
                url=f"https://graph.microsoft.com/v1.0/servicePrincipals/{id}",
                headers=graph_api_headers,
            ).json()["appDisplayName"]
            if type == "ServicePrincipal"
            else f"Identity '{id}' not found"
        )

    except requests.exceptions.RequestException as e:
        raise SystemExit(e)


def main(msg: func.QueueMessage) -> None:
    logging.info(
        json.dumps((payload := json.loads(msg.get_body().decode("utf-8"))), indent=4)
    )
    filters = [
        payload["data"]["authorization"]["evidence"]["principalId"]
        not in [
            "75f443ce460a4175a70609ed6233173b",
            "d97620314333449ca8fb5c2c151e5b8d",
            "ae36e9b23e344b2cb0faf35a28e86638",
            "d772b9d2d41b41aca97282192e98bda8",
        ],
        "Microsoft.Security/advancedThreatProtectionSettings"
        not in (operation_name := payload["data"]["operationName"]),
        "Microsoft.Web/serverfarms/delete"
        not in (operation_name := payload["data"]["operationName"]),
        "Microsoft.Web/serverFarms/write"
        not in (operation_name := payload["data"]["operationName"]),
    ]
    if (
        all(filters)
        and sum(
            True for condition in ["delete", "write"] if condition in operation_name
        )
        >= 1
    ):
        try:
            rest_api_headers = get_api_headers(get_rest_api_token())
            graph_api_headers = get_api_headers(get_graph_api_token())
            subscription_name = get_subscription(
                payload["data"]["subscriptionId"], rest_api_headers
            )
            logging.info(
                requests.post(
                    url=os.environ["LOGICAPP_URI"],
                    json={
                        "upn": (
                            upn := (
                                requests.get(
                                    url=f"https://graph.microsoft.com/v1.0/servicePrincipals/{authorization['principalId']}",
                                    headers=graph_api_headers,
                                )
                                .json()
                                .get(
                                    "appDisplayName",
                                    f"Identity '{authorization['principalId']}' not found",
                                )
                                if (
                                    authorization := payload["data"]["authorization"][
                                        "evidence"
                                    ]
                                )["principalType"]
                                == "ServicePrincipal"
                                else payload["data"]["claims"][
                                    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
                                ]
                            )
                        ),
                        "id": (id := payload["id"]),
                        "local_event_time": (
                            local_event_time := str(
                                datetime.datetime.now(
                                    pytz.timezone("Australia/Melbourne")
                                )
                            )[:-13]
                        ),
                        "correlation_id": (
                            correlation_id := payload["data"]["correlationId"]
                        ),
                        "operation_name": operation_name,
                        "action_status": (action_status := payload["data"]["status"]),
                        "resource_id": (resource_id := payload["data"]["resourceUri"]),
                        "subscription_name": subscription_name,
                    },
                )
            )
            if "@" in upn:
                account_keys = os.environ["AZUREMONITOREVENTSTRGE_CONNECTION"].split(
                    ";"
                )
                table_service = TableService(
                    account_name=account_keys[1][12:], account_key=account_keys[2][11:]
                )
                task = {
                    "PartitionKey": upn,
                    "RowKey": id,
                    "LocalEventTime": local_event_time,
                    "CorrelationId": correlation_id,
                    "OperationName": operation_name,
                    "ActionStatus": action_status,
                    "ResourceId": resource_id,
                    "SubscriptionName": subscription_name,
                }
                logging.info(
                    table_service.insert_entity("azuremonitoreventtable", task)
                )

        except requests.exceptions.RequestException as e:
            raise SystemExit(e)
