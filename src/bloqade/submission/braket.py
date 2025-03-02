from bloqade.submission.base import SubmissionBackend
from bloqade.submission.ir.braket import (
    from_braket_task_results,
    from_braket_status_codes,
    to_braket_task,
)
from bloqade.submission.ir.task_results import (
    QuEraTaskStatusCode,
    QuEraTaskResults,
)
from bloqade.submission.ir.task_specification import QuEraTaskSpecification
from braket.aws import AwsDevice, AwsQuantumTask


class BraketBackend(SubmissionBackend):
    device_arn: str = "arn:aws:braket:us-east-1::device/qpu/quera/Aquila"

    @property
    def device(self) -> AwsDevice:
        return AwsDevice(self.device_arn)

    def submit_task(self, task_ir: QuEraTaskSpecification) -> str:
        shots, ahs_program = to_braket_task(task_ir)
        task = self.device.run(ahs_program, shots=shots)
        return task.id

    def task_results(self, task_id: str) -> QuEraTaskResults:
        return from_braket_task_results(AwsQuantumTask(task_id).result())

    def cancel_task(self, task_id: str) -> None:
        AwsQuantumTask(task_id).cancel()

    def task_status(self, task_id: str) -> QuEraTaskStatusCode:
        return from_braket_status_codes(AwsQuantumTask(task_id).state())

    def validate_task(self, task_ir: QuEraTaskSpecification):
        pass

    # def validate_task(self, task_ir: QuEraTaskSpecification):
    #     try:
    #         task_id = self.submit_task(task_ir)
    #     except Exception as e:
    #         if "ValidationException" in str(e) and "validation error" in str(e):
    #             raise ValidationError(str(e))
    #         else:
    #             raise e

    #     # don't want the task to actually run
    #     try:
    #         self.cancel_task(task_id)
    #     except Exception as e:
    #         return
