"""Small thermal protocol retained for compiler tests."""

from lab import Plate, Protocol, Well, celsius, seconds, uL


def thermal_aliquots() -> Protocol:
    p = Protocol(
        "Stage composition with water",
        description="Compiler fixture: named transfers and two thermal profiles.",
    )
    water = p.container(
        "water", contents="water", volume=300 * uL, capacity=300 * uL, dead_volume=20 * uL
    )
    plate = p.plate("aliquots", capacity=100 * uL)
    assembled = _assembly(p, water, plate)
    transformed = _transformation(p, assembled, plate)
    _plating(p, transformed, (plate["A3"], plate["A4"]))
    return p


def _assembly(p: Protocol, water: Well, plate: Plate) -> Well:
    product = plate["A1"]
    for _ in range(2):
        p.transfer(water, product, volume=50 * uL)
    p.mix(product, volume=25 * uL, cycles=2)
    p.thermocycle(
        plate,
        [(celsius(25), 1 * seconds), (celsius(30), 1 * seconds)],
        cycles=2,
        lid_temperature=celsius(40),
    )
    return product


def _transformation(p: Protocol, previous: Well, plate: Plate) -> Well:
    product = plate["A2"]
    p.transfer(previous, product, volume=50 * uL)
    p.thermocycle(plate, [(celsius(25), 1 * seconds)])
    return product


def _plating(p: Protocol, previous: Well, destinations: tuple[Well, ...]) -> tuple[Well, ...]:
    for destination in destinations:
        p.transfer(previous, destination, volume=25 * uL)
    return destinations
