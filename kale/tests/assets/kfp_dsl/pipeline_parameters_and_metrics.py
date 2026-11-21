import json
import kfp.dsl as kfp_dsl
from kfp.dsl import Input, Output, Dataset, HTML, Metrics, Artifact, Model
from kfp.kubernetes import add_pod_annotation, add_pod_label, security_context, use_secret_as_env


@kfp_dsl.component(
    base_image='python:3.12',
    packages_to_install=['kfp>=2.0.0', 'kubeflow-kale', 'numpy'],
    pip_index_urls=['https://pypi.org/simple'],
    pip_trusted_hosts=[]
)
def create_matrix_step(create_matrix_html_report: Output[HTML], kale_metrics_artifact: Output[Metrics], rnd_matrix_output_artifact: Output[Dataset], d1: int = 5, d2: int = 6, booltest: bool = True, strtest: str = 'test'):
    _kale_pipeline_parameters_block = f'''
        d1 = {d1}
        d2 = {d2}
        booltest = {booltest}
        strtest = '{strtest}'
    '''

    _kale_data_loading_block = '''
    # -----------------------DATA LOADING START--------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # -----------------------DATA LOADING END----------------------------------
    '''

    _kale_block1 = '''
    import numpy as np
    '''

    _kale_block2 = '''
    rnd_matrix = np.random.rand(d1, d2)
    '''

    _kale_block3 = '''
    from kale.common import kfputils as _kale_kfputils
    _kale_kfp_metrics = {
        "d1": d1,
        "d2": d2
    }
    _kale_kfputils.generate_mlpipeline_metrics(_kale_kfp_metrics)
    '''

    _kale_data_saving_block = '''
    # -----------------------DATA SAVING START---------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # Save rnd_matrix to output artifact
    _ = _kale_marshal.save(rnd_matrix, "rnd_matrix_artifact")
    # -----------------------DATA SAVING END-----------------------------------
    '''

    # run the code blocks inside a jupyter kernel
    from kale.common.jputils import run_code as _kale_run_code

    _kale_blocks = (
        _kale_pipeline_parameters_block,
        _kale_data_loading_block,

        _kale_block1,
        _kale_block2,
        _kale_block3,
        _kale_data_saving_block
    )

    _kale_html_artifact = _kale_run_code(_kale_blocks)
    with open(create_matrix_html_report.path, "w") as f:
        f.write(_kale_html_artifact)
    # Prepare output artifacts to be retrieved during the pipeline execution
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    import shutil as _shutil

    artifact_path = _kale_marshal.get_path("rnd_matrix_artifact")
    _shutil.copyfile(artifact_path, rnd_matrix_output_artifact.path)
    rnd_matrix_output_artifact.metadata["marshal_path"] = artifact_path
    from kale.common.kfputils import load_mlpipeline_metrics
    load_mlpipeline_metrics(kale_metrics_artifact)


@kfp_dsl.component(
    base_image='python:3.12',
    packages_to_install=['kfp>=2.0.0', 'kubeflow-kale', 'numpy'],
    pip_index_urls=['https://pypi.org/simple'],
    pip_trusted_hosts=[]
)
def sum_matrix_step(sum_matrix_html_report: Output[HTML], kale_metrics_artifact: Output[Metrics], rnd_matrix_input_artifact: Input[Dataset], d1: int = 5, d2: int = 6, booltest: bool = True, strtest: str = 'test'):
    _kale_pipeline_parameters_block = f'''
        d1 = {d1}
        d2 = {d2}
        booltest = {booltest}
        strtest = '{strtest}'
    '''
    # Saves the received artifacts to be retrieved during the nb execution
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    import shutil as _shutil
    artifact_path = rnd_matrix_input_artifact.metadata["marshal_path"]
    if artifact_path is not None:
        _shutil.copy(rnd_matrix_input_artifact.path, artifact_path)

    _kale_data_loading_block = '''
    # -----------------------DATA LOADING START--------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # Load rnd_matrix_artifact from input artifact
    rnd_matrix = _kale_marshal.load("rnd_matrix_artifact")
    # -----------------------DATA LOADING END----------------------------------
    '''

    _kale_block1 = '''
    import numpy as np
    '''

    _kale_block2 = '''
    sum_result = rnd_matrix.sum()
    '''

    _kale_block3 = '''
    from kale.common import kfputils as _kale_kfputils
    _kale_kfp_metrics = {
        "sum-result": sum_result
    }
    _kale_kfputils.generate_mlpipeline_metrics(_kale_kfp_metrics)
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
        _kale_block3,
        _kale_data_saving_block
    )

    _kale_html_artifact = _kale_run_code(_kale_blocks)
    with open(sum_matrix_html_report.path, "w") as f:
        f.write(_kale_html_artifact)
    from kale.common.kfputils import load_mlpipeline_metrics
    load_mlpipeline_metrics(kale_metrics_artifact)


@kfp_dsl.pipeline(
    name='hp-test',
    description=''
)
def auto_generated_pipeline(d1: int = 5, d2: int = 6, booltest: bool = True, strtest: str = 'test'):
    """Auto-generated pipeline function."""

    create_matrix_task = create_matrix_step(
        d1=d1,
        d2=d2,
        booltest=booltest,
        strtest=strtest
    )

    security_context.set_security_context(
        task=create_matrix_task,
        run_as_user=65534,
        run_as_group=0,
        run_as_non_root=True
    )
    create_matrix_task.set_env_variable(name="HOME", value="/tmp")

    create_matrix_task.set_display_name("create-matrix-step")

    create_matrix_task.set_caching_options(enable_caching=True)
    create_matrix_task.set_accelerator_type(
        "nvidia.com/gpu").set_accelerator_limit(2)

    sum_matrix_task = sum_matrix_step(
        rnd_matrix_input_artifact=create_matrix_task.outputs["rnd_matrix_output_artifact"],
        d1=d1,
        d2=d2,
        booltest=booltest,
        strtest=strtest
    )

    security_context.set_security_context(
        task=sum_matrix_task,
        run_as_user=65534,
        run_as_group=0,
        run_as_non_root=True
    )
    sum_matrix_task.set_env_variable(name="HOME", value="/tmp")
    sum_matrix_task.after(create_matrix_task)

    sum_matrix_task.set_display_name("sum-matrix-step")

    sum_matrix_task.set_caching_options(enable_caching=False)


if __name__ == "__main__":
    from kfp import compiler

    compiler.Compiler().compile(auto_generated_pipeline, "hp-test.yaml")

    print("Pipeline compiled to hp-test.yaml")
    print("To run, upload this YAML to your KFP v2 instance or use kfp.Client().create_run_from_pipeline_func.")
