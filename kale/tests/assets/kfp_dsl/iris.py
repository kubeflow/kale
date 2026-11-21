import json
import kfp.dsl as kfp_dsl
from kfp.dsl import Input, Output, Dataset, HTML, Metrics, Artifact, Model
from kfp.kubernetes import add_pod_annotation, add_pod_label, security_context, use_secret_as_env


@kfp_dsl.component(
    base_image='python:3.12',
    packages_to_install=['kfp>=2.0.0',
                         'kubeflow-kale', 'numpy', 'scikit-learn'],
    pip_index_urls=['https://pypi.org/simple'],
    pip_trusted_hosts=[]
)
def load_transform_data_step(x_trn_output_artifact: Output[Dataset], x_tst_output_artifact: Output[Dataset], y_trn_output_artifact: Output[Dataset], y_tst_output_artifact: Output[Dataset], n_estimators_param: int = 500, max_depth_param: int = 2):
    _kale_pipeline_parameters_block = f'''
        N_ESTIMATORS = {n_estimators_param}
        MAX_DEPTH = {max_depth_param}
    '''

    _kale_data_loading_block = '''
    # -----------------------DATA LOADING START--------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # -----------------------DATA LOADING END----------------------------------
    '''

    _kale_block1 = '''
    import sklearn
    import numpy as np
    
    from sklearn import datasets
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
    '''

    _kale_block2 = '''
    x, y = datasets.load_iris(return_X_y=True)
    '''

    _kale_block3 = '''
    x_trn, x_tst, y_trn, y_tst = train_test_split(x, y, test_size=.2)
    '''

    _kale_data_saving_block = '''
    # -----------------------DATA SAVING START---------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # Save x_trn to output artifact
    _ = _kale_marshal.save(x_trn, "x_trn_artifact")
    # Save x_tst to output artifact
    _ = _kale_marshal.save(x_tst, "x_tst_artifact")
    # Save y_trn to output artifact
    _ = _kale_marshal.save(y_trn, "y_trn_artifact")
    # Save y_tst to output artifact
    _ = _kale_marshal.save(y_tst, "y_tst_artifact")
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

    _kale_run_code(_kale_blocks)
    # Prepare output artifacts to be retrieved during the pipeline execution
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    import shutil as _shutil

    artifact_path = _kale_marshal.get_path("x_trn_artifact")
    _shutil.copyfile(artifact_path, x_trn_output_artifact.path)
    x_trn_output_artifact.metadata["marshal_path"] = artifact_path
    artifact_path = _kale_marshal.get_path("x_tst_artifact")
    _shutil.copyfile(artifact_path, x_tst_output_artifact.path)
    x_tst_output_artifact.metadata["marshal_path"] = artifact_path
    artifact_path = _kale_marshal.get_path("y_trn_artifact")
    _shutil.copyfile(artifact_path, y_trn_output_artifact.path)
    y_trn_output_artifact.metadata["marshal_path"] = artifact_path
    artifact_path = _kale_marshal.get_path("y_tst_artifact")
    _shutil.copyfile(artifact_path, y_tst_output_artifact.path)
    y_tst_output_artifact.metadata["marshal_path"] = artifact_path


@kfp_dsl.component(
    base_image='python:3.12',
    packages_to_install=['kfp>=2.0.0',
                         'kubeflow-kale', 'numpy', 'scikit-learn'],
    pip_index_urls=['https://pypi.org/simple'],
    pip_trusted_hosts=[]
)
def train_model_step(train_model_html_report: Output[HTML], x_trn_input_artifact: Input[Dataset], y_trn_input_artifact: Input[Dataset], model_output_artifact: Output[Model], n_estimators_param: int = 500, max_depth_param: int = 2):
    _kale_pipeline_parameters_block = f'''
        N_ESTIMATORS = {n_estimators_param}
        MAX_DEPTH = {max_depth_param}
    '''
    # Saves the received artifacts to be retrieved during the nb execution
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    import shutil as _shutil
    artifact_path = x_trn_input_artifact.metadata["marshal_path"]
    if artifact_path is not None:
        _shutil.copy(x_trn_input_artifact.path, artifact_path)
    artifact_path = y_trn_input_artifact.metadata["marshal_path"]
    if artifact_path is not None:
        _shutil.copy(y_trn_input_artifact.path, artifact_path)

    _kale_data_loading_block = '''
    # -----------------------DATA LOADING START--------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # Load x_trn_artifact from input artifact
    x_trn = _kale_marshal.load("x_trn_artifact")
    # Load y_trn_artifact from input artifact
    y_trn = _kale_marshal.load("y_trn_artifact")
    # -----------------------DATA LOADING END----------------------------------
    '''

    _kale_block1 = '''
    import sklearn
    import numpy as np
    
    from sklearn import datasets
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
    '''

    _kale_block2 = '''
    model = RandomForestClassifier(n_estimators=int(N_ESTIMATORS),
                                   max_depth=int(MAX_DEPTH))
    '''

    _kale_block3 = '''
    model.fit(x_trn, y_trn)
    '''

    _kale_data_saving_block = '''
    # -----------------------DATA SAVING START---------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # Save model to output artifact
    _ = _kale_marshal.save(model, "model_artifact")
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
    with open(train_model_html_report.path, "w") as f:
        f.write(_kale_html_artifact)
    # Prepare output artifacts to be retrieved during the pipeline execution
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    import shutil as _shutil

    artifact_path = _kale_marshal.get_path("model_artifact")
    _shutil.copyfile(artifact_path, model_output_artifact.path)
    model_output_artifact.metadata["marshal_path"] = artifact_path


@kfp_dsl.component(
    base_image='python:3.12',
    packages_to_install=['kfp>=2.0.0',
                         'kubeflow-kale', 'numpy', 'scikit-learn'],
    pip_index_urls=['https://pypi.org/simple'],
    pip_trusted_hosts=[]
)
def evaluate_model_step(kale_metrics_artifact: Output[Metrics], model_input_artifact: Input[Model], x_tst_input_artifact: Input[Dataset], y_tst_input_artifact: Input[Dataset], n_estimators_param: int = 500, max_depth_param: int = 2):
    _kale_pipeline_parameters_block = f'''
        N_ESTIMATORS = {n_estimators_param}
        MAX_DEPTH = {max_depth_param}
    '''
    # Saves the received artifacts to be retrieved during the nb execution
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    import shutil as _shutil
    artifact_path = model_input_artifact.metadata["marshal_path"]
    if artifact_path is not None:
        _shutil.copy(model_input_artifact.path, artifact_path)
    artifact_path = x_tst_input_artifact.metadata["marshal_path"]
    if artifact_path is not None:
        _shutil.copy(x_tst_input_artifact.path, artifact_path)
    artifact_path = y_tst_input_artifact.metadata["marshal_path"]
    if artifact_path is not None:
        _shutil.copy(y_tst_input_artifact.path, artifact_path)

    _kale_data_loading_block = '''
    # -----------------------DATA LOADING START--------------------------------
    from kale import marshal as _kale_marshal
    _kale_marshal.set_data_dir("/tmp/marshal")
    # Load model_artifact from input artifact
    model = _kale_marshal.load("model_artifact")
    # Load x_tst_artifact from input artifact
    x_tst = _kale_marshal.load("x_tst_artifact")
    # Load y_tst_artifact from input artifact
    y_tst = _kale_marshal.load("y_tst_artifact")
    # -----------------------DATA LOADING END----------------------------------
    '''

    _kale_block1 = '''
    import sklearn
    import numpy as np
    
    from sklearn import datasets
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
    '''

    _kale_block2 = '''
    preds = model.predict(x_tst)
    '''

    _kale_block3 = '''
    precision = precision_score(y_tst, preds, average='macro')
    recall = recall_score(y_tst, preds, average='macro')
    f1 = f1_score(y_tst, preds, average='macro')
    accuracy = accuracy_score(y_tst, preds)
    '''

    _kale_block4 = '''
    from kale.common import kfputils as _kale_kfputils
    _kale_kfp_metrics = {
        "accuracy": accuracy,
        "f1": f1,
        "precision": precision,
        "recall": recall
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
        _kale_block4,
        _kale_data_saving_block
    )

    _kale_run_code(_kale_blocks)
    from kale.common.kfputils import load_mlpipeline_metrics
    load_mlpipeline_metrics(kale_metrics_artifact)


@kfp_dsl.pipeline(
    name='iris-pipeline',
    description='Train a Random Forest classifier on the Iris dataset'
)
def auto_generated_pipeline(n_estimators: int = 500, max_depth: int = 2):
    """Auto-generated pipeline function."""

    load_transform_data_task = load_transform_data_step(
        n_estimators_param=n_estimators,
        max_depth_param=max_depth
    )

    security_context.set_security_context(
        task=load_transform_data_task,
        run_as_user=65534,
        run_as_group=0,
        run_as_non_root=True
    )
    load_transform_data_task.set_env_variable(name="HOME", value="/tmp")

    load_transform_data_task.set_display_name("load-transform-data-step")

    load_transform_data_task.set_caching_options(enable_caching=False)
    add_pod_label(task=load_transform_data_task,
                  label_key="access-ml-pipeline", label_value="true")

    train_model_task = train_model_step(
        x_trn_input_artifact=load_transform_data_task.outputs["x_trn_output_artifact"],
        y_trn_input_artifact=load_transform_data_task.outputs["y_trn_output_artifact"],
        n_estimators_param=n_estimators,
        max_depth_param=max_depth
    )

    security_context.set_security_context(
        task=train_model_task,
        run_as_user=65534,
        run_as_group=0,
        run_as_non_root=True
    )
    train_model_task.set_env_variable(name="HOME", value="/tmp")
    train_model_task.after(load_transform_data_task)

    train_model_task.set_display_name("train-model-step")

    train_model_task.set_caching_options(enable_caching=False)
    add_pod_label(task=train_model_task,
                  label_key="access-ml-pipeline", label_value="true")

    evaluate_model_task = evaluate_model_step(
        model_input_artifact=train_model_task.outputs["model_output_artifact"],
        x_tst_input_artifact=load_transform_data_task.outputs["x_tst_output_artifact"],
        y_tst_input_artifact=load_transform_data_task.outputs["y_tst_output_artifact"],
        n_estimators_param=n_estimators,
        max_depth_param=max_depth
    )

    security_context.set_security_context(
        task=evaluate_model_task,
        run_as_user=65534,
        run_as_group=0,
        run_as_non_root=True
    )
    evaluate_model_task.set_env_variable(name="HOME", value="/tmp")
    evaluate_model_task.after(load_transform_data_task)
    evaluate_model_task.after(train_model_task)

    evaluate_model_task.set_display_name("evaluate-model-step")

    evaluate_model_task.set_caching_options(enable_caching=False)
    add_pod_label(task=evaluate_model_task,
                  label_key="access-ml-pipeline", label_value="true")


if __name__ == "__main__":
    from kfp import compiler

    compiler.Compiler().compile(auto_generated_pipeline, "iris-pipeline.yaml")

    print("Pipeline compiled to iris-pipeline.yaml")
    print("To run, upload this YAML to your KFP v2 instance or use kfp.Client().create_run_from_pipeline_func.")
