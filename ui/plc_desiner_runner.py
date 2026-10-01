from pathlib import Path
import subprocess


DEFAULT_PLC_DESIGNER = (
    r"C:\Program Files\Lenze\PlcDesigner"
    r"\4.2.0.41765\PlcDesigner\Common\PlcDesigner.exe"
)


class PLCDesignerRunner:

    def __init__(self, exe_path=None):

        self.exe_path = (
            exe_path
            or DEFAULT_PLC_DESIGNER
        )

    def exists(self):

        return Path(
            self.exe_path
        ).exists()

    def launch(self):

        if not self.exists():

            raise FileNotFoundError(
                self.exe_path
            )

        subprocess.Popen(
            [self.exe_path]
        )

        return True