import json
import kfp.dsl as kfp_dsl
from kfp.dsl import Input, Output, Dataset, HTML, Metrics, Artifact, Model
from kfp.kubernetes import add_pod_annotation, add_pod_label, security_context, use_secret_as_env
from kfp import kubernetes


@kfp_dsl.component(
    base_image='python:3.12',
    packages_to_install=['kfp>=2.0.0', 'kubeflow-kale'],
    pip_index_urls=['https://pypi.org/simple'],
    pip_trusted_hosts=[]
)
def load_step(load_html_report: Output[HTML]):
    _kale_pipeline_parameters_block = f'''
    '''

    _kale_data_loading_block = '''
    # -----------------------DATA LOADING START--------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # -----------------------DATA LOADING END----------------------------------
    '''

    _kale_block1 = '''
    import os
    '''

    _kale_block2 = '''
    data_path = "/data/input.csv"
    '''

    _kale_data_saving_block = '''
    # -----------------------DATA SAVING START---------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # -----------------------DATA SAVING END-----------------------------------
    '''

    # run the code blocks inside a jupyter kernel
    from kale.common.jputils import run_code as _kale_run_code

    _kale_blocks = (
        _kale_pipeline_parameters_block,
        _kale_data_loading_block,

        _kale_block1,
        _kale_block2,
        _kale_data_saving_block
    )

    _kale_html_artifact = _kale_run_code(_kale_blocks)
    with open(load_html_report.path, "w") as f:
        f.write(_kale_html_artifact)


@kfp_dsl.component(
    base_image='python:3.12',
    packages_to_install=['kfp>=2.0.0', 'kubeflow-kale'],
    pip_index_urls=['https://pypi.org/simple'],
    pip_trusted_hosts=[]
)
def train_step(train_html_report: Output[HTML]):
    _kale_pipeline_parameters_block = f'''
    '''

    _kale_data_loading_block = '''
    # -----------------------DATA LOADING START--------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # -----------------------DATA LOADING END----------------------------------
    '''

    _kale_block1 = '''
    import os
    '''

    _kale_block2 = '''
    result = data_path + "_trained"
    '''

    _kale_data_saving_block = '''
    # -----------------------DATA SAVING START---------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # -----------------------DATA SAVING END-----------------------------------
    '''

    # run the code blocks inside a jupyter kernel
    from kale.common.jputils import run_code as _kale_run_code

    _kale_blocks = (
        _kale_pipeline_parameters_block,
        _kale_data_loading_block,

        _kale_block1,
        _kale_block2,
        _kale_data_saving_block
    )

    _kale_html_artifact = _kale_run_code(_kale_blocks)
    with open(train_html_report.path, "w") as f:
        f.write(_kale_html_artifact)


@kfp_dsl.pipeline(
    name='mount-pvc-test',
    description='Test PVC mounting'
)
def auto_generated_pipeline():
    """Auto-generated pipeline function."""

    load_task = load_step(
    )

    security_context.set_security_context(
        task=load_task,
        run_as_user=65534,
        run_as_group=0,
        run_as_non_root=True
    )
    load_task.set_env_variable(name="HOME", value="/tmp")

    load_task.set_display_name("load-step")

    kubernetes.mount_pvc(load_task, pvc_name="raw-data", mount_path="/data")

    train_task = train_step(
    )

    security_context.set_security_context(
        task=train_task,
        run_as_user=65534,
        run_as_group=0,
        run_as_non_root=True
    )
    train_task.set_env_variable(name="HOME", value="/tmp")
    train_task.after(load_task)

    train_task.set_display_name("train-step")

    kubernetes.mount_pvc(train_task, pvc_name="raw-data", mount_path="/data")


if __name__ == "__main__":
    from kfp import compiler

    compiler.Compiler().compile(auto_generated_pipeline, "mount-pvc-test.yaml")

    print("Pipeline compiled to mount-pvc-test.yaml")
    print("To run, upload this YAML to your KFP v2 instance or use kfp.Client().create_run_from_pipeline_func.")
