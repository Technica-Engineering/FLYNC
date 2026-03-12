from pydantic import BaseModel

from .ids import ObjectId


class SemanticObject(object):
    """Wrapper around a validated semantic model.

    Attributes:
        id (ObjectId): Identifier of the semantic object.
        model (BaseModel): The validated Pydantic model.
    """

    def __init__(self, id: ObjectId, model: BaseModel):
        """Initialize a SemanticObject.

        Args:
            id (ObjectId): Identifier of the semantic object.
            model (BaseModel): The validated Pydantic model.
        """
        self.id = id
        self.model = model
