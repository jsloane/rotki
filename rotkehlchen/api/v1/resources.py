from typing import Any, Dict, List, Optional

from flask import Blueprint, Flask
from flask_restful import Resource
from webargs.flaskparser import use_kwargs

from rotkehlchen.api.v1.encoding import (
    ExchangeBalanceQuerySchema,
    NewUserSchema,
    TradePatchSchema,
    TradeSchema,
    TradesQuerySchema,
    UserActionSchema,
)
from rotkehlchen.assets.asset import Asset
from rotkehlchen.typing import AssetAmount, Fee, Location, Price, Timestamp, TradeType


def create_blueprint():
    # Take a look at this SO question on hints how to organize versioned
    # API with flask:
    # http://stackoverflow.com/questions/28795561/support-multiple-api-versions-in-flask#28797512
    return Blueprint("v1_resources", __name__)


class BaseResource(Resource):
    def __init__(self, rest_api_object, **kwargs):
        super().__init__(**kwargs)
        self.rest_api = rest_api_object


class SettingsResource(BaseResource):

    def put(self, settings: Dict[str, Any]) -> Flask.response_class:
        return self.rest_api.set_settings(settings)

    def get(self) -> Flask.response_class:
        return self.rest_api.get_settings()


class TaskOutcomeResource(BaseResource):

    def get(self, task_id: int) -> Flask.response_class:
        return self.rest_api.query_task_outcome(task_id=task_id)


class FiatExchangeRatesResource(BaseResource):

    def get(self, currencies: List[str]) -> Flask.response_class:
        return self.rest_api.get_fiat_exchange_rates(currencies=currencies)


class ExchangesResource(BaseResource):

    def put(self, name: str, api_key: str, api_secret: str) -> Flask.response_class:
        return self.rest_api.setup_exchange(name, api_key, api_secret)

    def delete(self, name: str) -> Flask.response_class:
        return self.rest_api.remove_exchange(name=name)


class ExchangeBalancesResource(BaseResource):

    get_schema = ExchangeBalanceQuerySchema()

    @use_kwargs(get_schema, locations=('json',))
    def get(self, name: str, async_query: bool) -> Flask.response_class:
        return self.rest_api.query_exchange_balances(name=name, async_query=async_query)


class TradesResource(BaseResource):

    get_schema = TradesQuerySchema()
    put_schema = TradeSchema()
    patch_schema = TradePatchSchema()

    @use_kwargs(get_schema, locations=('json',))
    def get(
            self,
            from_timestamp: Optional[Timestamp],
            to_timestamp: Optional[Timestamp],
            location: Optional[Location],
    ) -> Flask.response_class:
        return self.rest_api.get_trades(
            from_ts=from_timestamp,
            to_ts=to_timestamp,
            location=location,
        )

    @use_kwargs(put_schema, locations=('json',))
    def put(
            self,
            timestamp: Timestamp,
            location: Location,
            pair: str,
            trade_type: TradeType,
            amount: AssetAmount,
            rate: Price,
            fee: Fee,
            fee_currency: Asset,
            link: str,
            notes: str,
    ) -> Flask.response_class:
        return self.rest_api.add_trade(
            timestamp=timestamp,
            location=location,
            pair=pair,
            trade_type=trade_type,
            amount=amount,
            rate=rate,
            fee=fee,
            fee_currency=fee_currency,
            link=link,
            notes=notes,
        )

    @use_kwargs(patch_schema, locations=('json',))
    def patch(
            self,
            trade_id: str,
            timestamp: Timestamp,
            pair: str,
            trade_type: TradeType,
            amount: AssetAmount,
            rate: Price,
            fee: Fee,
            fee_currency: Asset,
            link: str,
            notes: str,
    ) -> Flask.response_class:
        return self.rest_api.edit_trade(
            trade_id=trade_id,
            timestamp=timestamp,
            pair=pair,
            trade_type=trade_type,
            amount=amount,
            rate=rate,
            fee=fee,
            fee_currency=fee_currency,
            link=link,
            notes=notes,
        )

    def delete(self, trade_id: str) -> Flask.response_class:
        return self.rest_api.delete_external_trade(trade_id=trade_id)


class UsersResource(BaseResource):

    put_schema = NewUserSchema()

    def get(self) -> Flask.response_class:
        return self.rest_api.get_users()

    @use_kwargs(put_schema, locations=('json',))
    def put(
            self,
            name: str,
            password: str,
            sync_approval: str,
            premium_api_key: str,
            premium_api_secret: str,
    ) -> Flask.response_class:
        return self.rest_api.create_new_user(
            name=name,
            password=password,
            sync_approval=sync_approval,
            premium_api_key=premium_api_key,
            premium_api_secret=premium_api_secret,
        )


class UsersByNameResource(BaseResource):
    patch_schema = UserActionSchema()

    @use_kwargs(patch_schema, locations=('json',))
    def patch(
            self,
            action: Optional[str],
            name: str,
            password: str,
            sync_approval: str,
            premium_api_key: str,
            premium_api_secret: str,
    ) -> Flask.response_class:
        if action is None:
            return self.rest_api.user_set_premium_credentials(
                name=name,
                api_key=premium_api_key,
                api_secret=premium_api_secret,
            )

        if action == 'login':
            return self.rest_api.user_login(
                name=name,
                password=password,
                sync_approval=sync_approval,
            )
        else:  # Can only be logout -- checked by marshmallow
            return self.rest_api.user_logout(name=name)
