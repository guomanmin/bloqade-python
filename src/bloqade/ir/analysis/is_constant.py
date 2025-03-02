import bloqade.ir.control.waveform as waveform
import bloqade.ir.control.field as field
import bloqade.ir.control.pulse as pulse
import bloqade.ir.control.sequence as sequence
import bloqade.ir.analog_circuit as analog_circuit
from bloqade.ir.visitor.waveform import WaveformVisitor
from bloqade.ir.visitor.analog_circuit import AnalogCircuitVisitor
from decimal import Decimal
from beartype.typing import Any, Dict
from beartype import beartype
from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class IsConstantWaveformResult:
    is_constant: bool
    constant_waveform: waveform.Constant


class IsConstantWaveform(WaveformVisitor):
    @beartype
    def __init__(self, assignments: Dict[str, Decimal]) -> None:
        self.assignments = dict(assignments)
        self.is_constant = True

    def visit_constant(self, _: waveform.Constant) -> Any:
        pass

    def visit_linear(self, ast: waveform.Linear) -> Any:
        diff = ast.stop(**self.assignments) - ast.start(**self.assignments)
        self.is_constant = self.is_constant and (diff == 0)

    def visit_poly(self, ast: waveform.Poly) -> Any:
        coeffs = [coeff(**self.assignments) for coeff in ast.coeffs]
        if any(coeff != 0 for coeff in coeffs[1:]):
            self.is_constant = False

    def visit_python_fn(self, ast: waveform.PythonFn) -> Any:
        # can't analyze python functions, assume it's not constant
        self.is_constant = False

    def visit_append(self, ast: waveform.Append) -> Any:
        value = None
        for wf in ast.waveforms:
            result = IsConstantWaveform(self.assignments).emit(wf)
            if value is None:
                value = result.constant_waveform.value

            self.is_constant = (self.is_constant and result.is_constant) and (
                result.constant_waveform.value == value
            )

            if not self.is_constant:
                return

    def visit_add(self, ast: waveform.Add) -> Any:
        left_duration = ast.left.duration(**self.assignments)
        right_duration = ast.right.duration(**self.assignments)

        if left_duration != right_duration:
            self.is_constant = False
            return

        self.visit(ast.left)
        self.visit(ast.right)

    def visit_alligned(self, ast: waveform.AlignedWaveform) -> Any:
        self.visit(ast.waveform)

    def visit_negative(self, ast: waveform.Negative) -> Any:
        self.visit(ast.waveform)

    def visit_record(self, ast: waveform.Record) -> Any:
        self.visit(ast.waveform)

    def visit_sample(self, ast: waveform.Sample) -> Any:
        self.visit(ast.waveform)

    def visit_scale(self, ast: waveform.Scale) -> Any:
        self.visit(ast.waveform)

    def visit_slice(self, ast: waveform.Slice) -> Any:
        self.visit(ast.waveform)

    def visit_smooth(self, ast: waveform.Smooth) -> Any:
        self.visit(ast.waveform)

    def emit(self, ast: waveform.Waveform) -> IsConstantWaveformResult:
        self.visit(ast)
        duration = ast.duration(**self.assignments)
        value = ast.eval_decimal(duration, **self.assignments)

        wf = waveform.Constant(value, duration)

        return IsConstantWaveformResult(self.is_constant, wf)


@dataclass(frozen=True)
class IsConstantAnalogCircuitResult:
    is_constant: bool
    effective_analog_circuit: analog_circuit.AnalogCircuit


class IsConstantAnalogCircuit(AnalogCircuitVisitor):
    # Note that this visitor is not complete, it only handles the cases that are
    # relevant for the current IR generated by the Builder semantics.

    @beartype
    def __init__(self, assignments: Dict[str, Decimal] = {}) -> None:
        self.assignments = dict(assignments)
        self.is_constant = True
        self.duration = None

    def visit_waveform(self, ast: waveform.Waveform):
        result = IsConstantWaveform(self.assignments).emit(ast)
        self.is_constant = self.is_constant and result.is_constant
        self.waveform = result.constant_waveform
        if self.duration is None:
            self.duration = self.waveform.duration(**self.assignments)
        else:
            if self.duration != self.waveform.duration(**self.assignments):
                self.is_constant = False

    def visit_field(self, ast: field.Field) -> Any:
        self.field = field.Field({})
        for sm, wf in ast.drives.items():
            self.visit(wf)

            self.field = self.field.add(field.Field({sm: self.waveform}))

    def visit_pulse(self, ast: pulse.Pulse) -> pulse.Pulse:
        self.pulse = pulse.Pulse({})
        for fn, fd in ast.fields.items():
            self.visit(fd)
            self.pulse.fields[fn] = self.field

    def visit_sequence(self, ast: sequence.Sequence) -> sequence.Sequence:
        self.sequence = sequence.Sequence({})
        for pn, ps in ast.pulses.items():
            self.visit(ps)
            self.sequence.pulses[pn] = self.pulse

    def visit_analog_circuit(self, ast: analog_circuit.AnalogCircuit) -> Any:
        self.visit(ast.sequence)
        self.analog_circuit = analog_circuit.AnalogCircuit(ast.register, self.sequence)

    def emit(self, ast: analog_circuit.AnalogCircuit) -> IsConstantAnalogCircuitResult:
        self.visit(ast)
        return IsConstantAnalogCircuitResult(self.is_constant, self.analog_circuit)
