"""Serial dilution and agar spotting recorded as ordinary protocol steps.

LB is added to every dilution well, each culture is diluted, and each dilution
is spotted once per replicate. Two dilution steps share one 96-well plate when
each step needs at most 48 wells; past that, each step gets its own plate.
Spotting addresses the well. The OT-2 protocol dispenses at the agar surface;
this record keeps the same well and volume.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from lab.experiments.cloning.addresses import microliters, well_at
from lab.protocol import Plate, Protocol, Well
from lab.units import celsius, uL


@dataclass(frozen=True)
class PlatingVolumes:
    bacteria: Decimal
    colony: Decimal
    factor: Decimal

    @property
    def lb(self) -> Decimal:
        return self.bacteria * (self.factor - 1)

    @property
    def mix(self) -> Decimal:
        return min(Decimal(19), self.lb + self.bacteria - 1)

    @property
    def diluted(self) -> Decimal:
        return self.bacteria * self.factor


def plating_plates(constructs: int, dilutions: int, replicates: int) -> tuple[bool, bool]:
    """Whether the dilution series and the agar spots each need a second plate."""
    return constructs * dilutions > 96, constructs * dilutions * replicates > 96


def record_plating(
    protocol: Protocol,
    sources: Sequence[Well],
    broth: Well,
    dilutions: Plate,
    agar: Plate,
    *,
    dilutions_2: Plate | None = None,
    agar_2: Plate | None = None,
    volume_bacteria_transfer: object = 2 * uL,
    volume_colony: object = 4 * uL,
    dilution_factor: object = 10,
    replicates: int = 1,
    number_dilutions: int = 2,
    hold_source: bool = True,
) -> None:
    """Dilute ``sources`` in order and spot ``replicates`` of each dilution."""
    volumes = _volumes(
        volume_bacteria_transfer, volume_colony, dilution_factor, replicates, number_dilutions
    )
    if hold_source and sources:
        plate = _plate_of(protocol, sources[0])
        if plate is not None:
            protocol.set_temperature(plate, celsius(4))
    dilution_a, dilution_b = _series(
        _column_major(dilutions),
        None if dilutions_2 is None else _column_major(dilutions_2),
        len(sources),
        number_dilutions,
    )
    agar_a, agar_b = _series(
        _column_major(agar),
        None if agar_2 is None else _column_major(agar_2),
        len(sources) * replicates,
        number_dilutions,
    )
    for well in (*dilution_a, *(dilution_b or ())):
        protocol.transfer(broth, well, volume=volumes.lb * uL)
    for index, source in enumerate(sources):
        protocol.transfer(source, dilution_a[index], volume=volumes.bacteria * uL)
        protocol.mix(dilution_a[index], volume=volumes.mix * uL, cycles=5)
        if dilution_b is not None and agar_b is not None:
            protocol.transfer(dilution_a[index], dilution_b[index], volume=volumes.bacteria * uL)
            protocol.mix(dilution_b[index], volume=volumes.mix * uL, cycles=5)
        for replicate in range(replicates):
            protocol.transfer(
                dilution_a[index],
                agar_a[index * replicates + replicate],
                volume=volumes.colony * uL,
            )
        if dilution_b is not None and agar_b is not None:
            for replicate in range(replicates):
                protocol.transfer(
                    dilution_b[index],
                    agar_b[index * replicates + replicate],
                    volume=volumes.colony * uL,
                )


def build_plating(
    bacterium_locations: Mapping[str, object],
    *,
    name: str = "Plating",
    volume_total_reaction: object = 20 * uL,
    volume_lb: object = 10000 * uL,
    volume_bacteria_transfer: object = 2 * uL,
    volume_colony: object = 4 * uL,
    dilution_factor: object = 10,
    replicates: int = 1,
    number_dilutions: int = 2,
    max_colonies: int = 192,
) -> Protocol:
    """Standalone plating protocol. Source wells are the mapping's keys, in order."""
    if not bacterium_locations:
        raise ValueError("bacterium_locations must be a non-empty dictionary")
    _volumes(
        volume_bacteria_transfer,
        volume_colony,
        dilution_factor,
        replicates,
        number_dilutions,
        constructs=len(bacterium_locations),
        max_colonies=max_colonies,
    )
    second_dilution, second_agar = plating_plates(
        len(bacterium_locations), number_dilutions, replicates
    )
    protocol = Protocol(name, description="Serial dilution and spotting onto an agar plate.")
    sources = protocol.plate("sources", shape=(8, 12), capacity=200 * uL, dead_volume=0 * uL)
    dilutions = protocol.plate("dilutions", shape=(8, 12), capacity=100 * uL, dead_volume=0 * uL)
    agar = protocol.plate("agar", shape=(8, 12), capacity=100 * uL, dead_volume=0 * uL)
    broth_plate = protocol.plate("broth", shape=(3, 5), capacity=15000 * uL, dead_volume=0 * uL)
    dilutions_2 = (
        protocol.plate("dilutions_2", shape=(8, 12), capacity=100 * uL, dead_volume=0 * uL)
        if second_dilution
        else None
    )
    agar_2 = (
        protocol.plate("agar_2", shape=(8, 12), capacity=100 * uL, dead_volume=0 * uL)
        if second_agar
        else None
    )
    for well, label in bacterium_locations.items():
        protocol.load(
            sources[str(well)],
            _label(label),
            volume=microliters(volume_total_reaction) * uL,
        )
    protocol.load(well_at(broth_plate, 0), "liquid_broth", volume=microliters(volume_lb) * uL)
    record_plating(
        protocol,
        [sources[str(well)] for well in bacterium_locations],
        well_at(broth_plate, 0),
        dilutions,
        agar,
        dilutions_2=dilutions_2,
        agar_2=agar_2,
        volume_bacteria_transfer=volume_bacteria_transfer,
        volume_colony=volume_colony,
        dilution_factor=dilution_factor,
        replicates=replicates,
        number_dilutions=number_dilutions,
    )
    return protocol


def _volumes(
    bacteria: object,
    colony: object,
    factor: object,
    replicates: int,
    dilutions: int,
    *,
    constructs: int | None = None,
    max_colonies: int = 192,
    well_capacity: Decimal = Decimal(100),
) -> PlatingVolumes:
    if type(replicates) is not int or replicates < 1:
        raise ValueError("Replicates must be a positive integer")
    if type(dilutions) is not int or not 1 <= dilutions <= 2:
        raise ValueError("Protocol currently supports a max of 2 dilutions")
    if replicates > 8:
        raise ValueError("Protocol only supports a max of 8 replicates")
    amount = microliters(bacteria)
    spot = microliters(colony)
    ratio = Decimal(str(factor))
    if ratio <= 1:
        raise ValueError("Dilution factor must be greater than 1")
    volumes = PlatingVolumes(amount, spot, ratio)
    needed = spot * replicates + (amount if dilutions > 1 else 0)
    if needed > volumes.diluted:
        raise ValueError(
            f"Dilution well volume ({volumes.diluted} µL) cannot supply {needed} µL of "
            "spotting and the next dilution."
        )
    if volumes.diluted > well_capacity:
        raise ValueError(
            f"Each dilution well needs {volumes.diluted} µL and the plate holds {well_capacity} µL."
        )
    if constructs is not None and constructs * dilutions * replicates > max_colonies:
        raise ValueError(f"Protocol only supports a max of {max_colonies} colonies")
    return volumes


def _series(
    primary: list[Well], other: list[Well] | None, count: int, dilutions: int
) -> tuple[list[Well], list[Well] | None]:
    if dilutions == 2 and count > 48:
        if other is None:
            raise ValueError("Two plates are required for this dilution series")
        return primary[:count], other[:count]
    if dilutions == 2:
        return primary[:count], primary[48 : 48 + count]
    return primary[:count], None


def _column_major(plate: Plate) -> list[Well]:
    rows, columns = plate.shape
    return [
        plate[f"{chr(65 + row)}{column + 1}"] for column in range(columns) for row in range(rows)
    ]


def _plate_of(protocol: Protocol, well: Well) -> Plate | None:
    for resource in protocol.snapshot().resources:
        if resource.name == well.resource:
            return Plate(resource.name, (resource.rows, resource.columns), well._owner)
    return None


def _label(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)
