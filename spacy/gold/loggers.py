from typing import Dict, Any, Tuple, Callable

from ..util import registry
from ..errors import Errors
from wasabi import msg


@registry.loggers("spacy.ConsoleLogger.v1")
def console_logger():
    def setup_printer(
        nlp: "Language"
    ) -> Tuple[Callable[[Dict[str, Any]], None], Callable]:
        score_cols = list(nlp.config["training"]["score_weights"])
        score_widths = [max(len(col), 6) for col in score_cols]
        loss_cols = [f"Loss {pipe}" for pipe in nlp.pipe_names]
        loss_widths = [max(len(col), 8) for col in loss_cols]
        table_header = ["E", "#"] + loss_cols + score_cols + ["Score"]
        table_header = [col.upper() for col in table_header]
        table_widths = [3, 6] + loss_widths + score_widths + [6]
        table_aligns = ["r" for _ in table_widths]
        msg.row(table_header, widths=table_widths)
        msg.row(["-" * width for width in table_widths])

        def log_step(info: Dict[str, Any]):
            try:
                losses = [
                    "{0:.2f}".format(float(info["losses"][pipe_name]))
                    for pipe_name in nlp.pipe_names
                ]
            except KeyError as e:
                raise KeyError(
                    Errors.E983.format(
                        dict="scores (losses)",
                        key=str(e),
                        keys=list(info["losses"].keys()),
                    )
                ) from None

            try:
                scores = [
                    "{0:.2f}".format(float(info["other_scores"].get(col, 0.0)) * 100)
                    for col in score_cols
                ]
            except KeyError as e:
                raise KeyError(
                    Errors.E983.format(
                        dict="scores (other)",
                        key=str(e),
                        keys=list(info["other_scores"].keys()),
                    )
                ) from None
            data = (
                [info["epoch"], info["step"]]
                + losses
                + scores
                + ["{0:.2f}".format(float(info["score"]))]
            )
            msg.row(data, widths=table_widths, aligns=table_aligns)

        def finalize():
            pass

        return log_step, finalize

    return setup_printer


@registry.loggers("spacy.WandbLogger.v1")
def wandb_logger(project_name: str):
    import wandb

    console = console_logger()

    def setup_logger(
        nlp: "Language"
    ) -> Tuple[Callable[[Dict[str, Any]], None], Callable]:
        config = nlp.config.interpolate()
        wandb.init(project=project_name, config=config)
        console_log_step, console_finalize = console(nlp)

        def log_step(info: Dict[str, Any]):
            console_log_step(info)
            epoch = info["epoch"]
            score = info["score"]
            other_scores = info["other_scores"]
            losses = info["losses"]
            wandb.log({"score": score, "epoch": epoch})
            if losses:
                wandb.log({f"loss_{k}": v for k, v in losses.items()})
            if isinstance(other_scores, dict):
                wandb.log(other_scores)

        def finalize():
            console_finalize()
            pass

        return log_step, finalize

    return setup_logger