from pydantic import BaseModel, Field, ConfigDict, PrivateAttr
from datetime import datetime
from typing import ClassVar, Dict, List, Type, TypeVar
from reclaim_sdk.client import ReclaimClient

T = TypeVar("T", bound="BaseResource")


class BaseResource(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: int | None = Field(None, description="Unique identifier of the resource")
    created: datetime | None = Field(None, description="Creation timestamp")
    updated: datetime | None = Field(None, description="Last update timestamp")

    ENDPOINT: ClassVar[str] = ""
    _client: ReclaimClient = PrivateAttr(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        if data.get("token"):
            self._client = ReclaimClient.configure(token=data["token"])
        else:
            self._client = ReclaimClient()

    @classmethod
    def from_api_data(cls: Type[T], data: Dict) -> T:
        return cls(**data)

    def to_api_data(self) -> Dict:
        return self.model_dump(exclude_unset=False, by_alias=True)

    @classmethod
    def get(cls: Type[T], id: int, client: ReclaimClient = None) -> T:
        if client is None:
            client = ReclaimClient()
        data = client.get(f"{cls.ENDPOINT}/{id}")
        instance = cls.from_api_data(data)
        instance._client = client
        return instance

    def refresh(self) -> None:
        if not self.id:
            raise ValueError("Cannot refresh a resource without an ID")
        client = self._client
        data = client.get(f"{self.ENDPOINT}/{self.id}")
        self.__dict__.update(self.from_api_data(data).__dict__)

    def save(self) -> None:
        client = self._client
        data = self.to_api_data()
        if self.id:
            response = client.patch(f"{self.ENDPOINT}/{self.id}", json=data)
        else:
            response = client.post(self.ENDPOINT, json=data)
        # Create a new instance with the response data and update current object
        new_instance = self.from_api_data(response)
        new_instance._client = client
        self.__dict__.update(new_instance.__dict__)

    def delete(self) -> None:
        if not self.id:
            raise ValueError("Cannot delete a resource without an ID")
        client = self._client
        client.delete(f"{self.ENDPOINT}/{self.id}")

    @classmethod
    def list(cls: Type[T], client: ReclaimClient = None, **params) -> List[T]:
        if client is None:
            client = ReclaimClient()
        data = client.get(cls.ENDPOINT, params=params)
        instances = []
        for item in data:
            instance = cls.from_api_data(item)
            instance._client = client
            instances.append(instance)
        return instances
