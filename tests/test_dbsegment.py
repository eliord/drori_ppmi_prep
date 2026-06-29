import numpy as np
import nibabel as nib

from drori_ppmi_prep.segmentation.dbsegment import create_gp_sn_segmentation


def test_create_gp_sn_segmentation_combines_subregion_labels(tmp_path):
    data = np.zeros((2, 4, 4), dtype=np.uint8)
    data[0, 0, 0] = 4
    data[0, 0, 1] = 6
    data[0, 1, 0] = 5
    data[0, 1, 1] = 7
    data[1, 0, 0] = 18
    data[1, 0, 1] = 20
    data[1, 1, 0] = 19
    data[1, 1, 1] = 21
    data[1, 2, 2] = 14

    input_file = tmp_path / "dbsegment.nii.gz"
    output_file = tmp_path / "derivatives" / "GP_SN_seg.nii.gz"
    nib.save(nib.Nifti1Image(data, np.eye(4)), input_file)

    output, status = create_gp_sn_segmentation(input_file, output_file)

    assert output == output_file
    assert status == "done"
    out = np.rint(nib.load(output_file).get_fdata()).astype(np.uint8)
    assert out[0, 0, 0] == 4
    assert out[0, 0, 1] == 4
    assert out[0, 1, 0] == 5
    assert out[0, 1, 1] == 5
    assert out[1, 0, 0] == 18
    assert out[1, 0, 1] == 18
    assert out[1, 1, 0] == 19
    assert out[1, 1, 1] == 19
    assert out[1, 2, 2] == 0
