import strawberry

from models.channels import ChannelQuery, ChannelMutation, ChannelSubscription
from models.messages import MessageQuery, MessageMutation, MessageSubscription
from models.users import UserQuery, UserMutation, UserSubscription


@strawberry.type
class Query(ChannelQuery, UserQuery, MessageQuery):
    pass


@strawberry.type
class Mutation(ChannelMutation, UserMutation, MessageMutation):
    pass


@strawberry.type
class Subscription(ChannelSubscription, UserSubscription, MessageSubscription):
    pass


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
