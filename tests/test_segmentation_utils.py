import numpy as np
import nibabel as nib

from drori_ppmi_prep.segmentation.utils import (
    erode_label_segmentation,
    matlab_sphere_1_structure,
)


def test_matlab_sphere_1_structure_matches_six_neighbors():
    structure = matlab_sphere_1_structure()

    assert structure.shape == (3, 3, 3)
    assert structure.sum() == 7
    assert structure[1, 1, 1]
    assert structure[0, 1, 1]
    assert structure[2, 1, 1]
    assert structure[1, 0, 1]
    assert structure[1, 2, 1]
    assert structure[1, 1, 0]
    assert structure[1, 1, 2]
    assert not structure[0, 0, 0]


def test_erode_label_segmentation_erodes_labels_independently(tmp_path):
    data = np.zeros((5, 5, 5), dtype=np.int16)
    data[1:4, 1:4, 1:4] = 12
    data[0, 0, 0] = 51
    image = nib.Nifti1Image(data, np.eye(4))

    input_file = tmp_path / "seg.nii.gz"
    output_file = tmp_path / "seg_eroded.nii.gz"
    nib.save(image, input_file)

    eroded = erode_label_segmentation(input_file, output_file)

    assert eroded == output_file
    out = np.rint(nib.load(output_file).get_fdata()).astype(np.int16)
    assert np.count_nonzero(out == 12) == 1
    assert out[2, 2, 2] == 12
    assert np.count_nonzero(out == 51) == 0
