from pyaml_env import parse_config
# config = BaseConfig(parse_config('/home/jsk/skill-prediction/jobxlmc/jobxmlc/configs/config.yaml'))

# flake8: noqa
from jobxmlc.registry import ENCODER_REGISTRY, DATA_FILTER_REGISTRY
from jobxmlc.core.utils import remove_key_from_dict, get_device
import argparse
from typing import Dict

def make_embeddings(encoder_parameters: Dict) -> None:
    encoder = ENCODER_REGISTRY[encoder_parameters["name"]](**remove_key_from_dict(encoder_parameters))
    encoder.embeddings_runner()
    return None


# def create_reporters(reporting: List[Dict], config_file: str):
#     reporting_hooks, reporting = merge_reporting_with_settings(reporting, {})
#     return create_reporting(reporting_hooks, reporting, {"config_file": config_file, "task": "eptest", "base_dir": "."})


def main():
    parser = argparse.ArgumentParser("train")
    parser.add_argument("--config_file", default="config/spr2.yml")
    args = parser.parse_args()
    exp_params = parse_config(args.config_file)
    make_embeddings(exp_params['encoder'])
    


    # model = create_model(exp_params["model"], data.id_2_label)
    # print(get_device())
    # if get_device().startswith("cuda"):
    #     model.cuda(get_device())
    # print("model loaded, loading reporters")

    # reporters = create_reporters(exp_params["reporting"], config_file=args.config_file)
    # print("reporters loaded, training")

    # train_params = exp_params["train"]
    # train_params["reporting"] = [x.step for x in reporters]
    # fit(model, ts=data.train, vs=data.dev, es=data.test["no_filter"], **train_params)
    # for reporter in reporters:
    #     reporter.done()


if __name__ == "__main__":
    main()