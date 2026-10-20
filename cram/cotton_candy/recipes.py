"""
Cotton candy flavours and their ingredients - the one source the booth's sugar cartons, the candy belief and the
ontology's materials share (twin register: colour_sugar_pink, SCHOKO/HOPSER/PCO sources).
"""

from __future__ import annotations

from enum import Enum

from typing_extensions import List


class Ingredient(Enum):
    """
    The ingredients of floss sugars, named as in the ontology (Material.name).
    """

    SUCROSE = "sucrose (floss sugar)"
    ALLURA_RED = "Allura Red (pink colour)"
    BRILLIANT_BLUE = "Brilliant Blue (blue colour)"
    SILICA = "silica (anti-caking agent)"
    LACTOSE = "lactose (carrier of the colour sugar)"
    FLAVOURING = "flavouring"


class Flavour(Enum):
    """
    The flavoured floss sugars (Farbzucker) the booth may sell.
    """

    RASPBERRY = "raspberry (pink)"
    BLUEBERRY = "blueberry (blue)"

    @property
    def ingredients(self) -> List[str]:
        """
        :return: The ingredient names of this flavour's floss sugar (SCHOKO: sugar, silica, lactose, colour, flavour).
        """
        colour = Ingredient.ALLURA_RED if self is Flavour.RASPBERRY else Ingredient.BRILLIANT_BLUE
        return [i.value for i in (Ingredient.SUCROSE, colour, Ingredient.SILICA, Ingredient.LACTOSE,
                                  Ingredient.FLAVOURING)]
