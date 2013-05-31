import numpy as np
from . import _marching_cubes_cy


def marching_cubes(volume, level, sampling=(1., 1., 1.)):
    """
    Marching cubes algorithm to find iso-valued surfaces in 3d volumetric data

    Parameters
    ----------
    volume : (M, N, P) array of doubles
        Input data volume to find isosurfaces. Will be cast to `np.float64` if
        not provided in this format.
    level : float
        Contour value to search for isosurfaces in `volume`.
    sampling : length-3 tuple of floats
        Voxel spacing in spatial dimensions corresponding to numpy array
        indexing dimensions (M, N, P) as in `volume`.

    Returns
    -------
    verts : (V, 3) array
        Spatial (x, y, z) coordinates for V unique vertices in mesh.
    faces : (F, 3) array
        Define triangular faces via referencing vertex indices from ``verts``.
        This algorithm specifically outputs triangles, so each face has
        exactly three indices.

    Notes
    -----
    The marching cubes algorithm is implemented as described in [1]_.
    A simple explanation is available here::

      http://www.essi.fr/~lingrand/MarchingCubes/algo.html

    There are several known ambiguous cases in the marching cubes algorithm.
    Using point labeling as in [1]_, Figure 4, as shown:

           v8 ------ v7
          / |       / |        y
         /  |      /  |        ^  z
       v4 ------ v3   |        | /
        |  v5 ----|- v6        |/          (note: NOT right handed!)
        | /       |  /          ----> x
        |/        | /
       v1 ------ v2

    Most notably, if v4, v8, v2, and v6 are all >= `level` (or any
    generalization of this case) two parallel planes are generated by this
    algorithm, separating v4 and v8 from v2 and v6. An equally valid
    interpretation would be a single connected thin surface enclosing all
    four points. This is the best known ambiguity, though there are others.

    This algorithm does not attempt to resolve such ambiguities; it is a naive
    implementation of marching cubes as in [1]_, but may be a good beginning
    for work with more recent techniques (Dual Marching Cubes, Extended
    Marching Cubes, Cubic Marching Squares, etc.).

    Because of interactions between neighboring cubes, the isosurface(s)
    generated by this algorithm are NOT guaranteed to be closed, particularly
    for complicated contours. Furthermore, this algorithm does not guarantee
    a single contour will be returned. Indeed, ALL isosurfaces which cross
    `level` will be found, regardless of connectivity.

    The output is a triangular mesh consisting of a set of unique vertices and
    connecting triangles. The order of these vertices and triangles in the
    output list is determined by the position of the smallest ``x,y,z`` (in
    lexicographical order) coordinate in the contour.  This is a side-effect
    of how the input array is traversed, but can be relied upon.

    To quantify the area of an isosurface generated by this algorithm, pass
    the outputs directly into `skimage.measure.mesh_surface_area`.

    Regarding visualization of algorithm output, the ``mayavi`` package
    is recommended. To contour a volume named `myvolume` about the level 0.0:

    >>> from mayavi import mlab
    >>> verts, tris = marching_cubes(myvolume, 0.0, (1., 1., 2.))
    >>> mlab.triangular_mesh([vert[0] for vert in verts],
                             [vert[1] for vert in verts],
                             [vert[2] for vert in verts],
                             tris)
    >>> mlab.show()

    References
    ----------
    .. [1] Lorensen, William and Harvey E. Cline. Marching Cubes: A High
           Resolution 3D Surface Construction Algorithm. Computer Graphics
           (SIGGRAPH 87 Proceedings) 21(4) July 1987, p. 163-170).

    See Also
    --------
    skimage.measure.mesh_surface_area

    """
    # Check inputs and ensure `volume` is C-contiguous for memoryviews
    if volume.ndim != 3:
        raise ValueError("Input volume must have 3 dimensions.")
    if level < volume.min() or level > volume.max():
        raise ValueError("Contour level must be within volume data range.")
    volume = np.array(volume, dtype=np.float64, order="C")

    # Extract raw triangles using marching cubes in Cython
    #   Returns a list of length-3 lists, each sub-list containing three
    #   tuples. The tuples hold (x, y, z) coordinates for triangle vertices.
    # Note: this algorithm is fast, but returns degenerate "triangles" which
    #   have repeated vertices - and equivalent vertices are redundantly
    #   placed in every triangle they connect with.
    raw_tris = _marching_cubes_cy.iterate_and_store_3d(volume, float(level),
                                                       sampling)

    # Find and collect unique vertices, storing triangle verts as indices.
    # Returns a true mesh with no degenerate faces.
    verts, faces = _marching_cubes_cy.unpack_unique_verts(raw_tris)

    return np.asarray(verts), np.asarray(faces)


def mesh_surface_area(verts, tris):
    """
    Compute surface area, given vertices & triangular faces

    Parameters
    ----------
    verts : (V, 3) array of floats
        Array containing (x, y, z) coordinates for V unique mesh vertices.
    faces : (F, 3) array of ints
        List of length-3 lists of integers, referencing vertex coordinates as
        provided in `verts`

    Returns
    -------
    area : float
        Surface area of mesh. Units now [coordinate units] ** 2.

    Notes
    -----
    The arguments expected by this function are the exact outputs from
    `skimage.measure.marching_cubes`. For unit correct output, ensure correct
    `spacing` was passed to `skimage.measure.marching_cubes`.

    This algorithm works properly only if the ``faces`` provided are all
    triangles.

    See Also
    --------
    skimage.measure.marching_cubes

    """
    # Fancy indexing to define two vector arrays from triangle vertices
    actual_verts = verts[tris]
    a = actual_verts[:, 0, :] - actual_verts[:, 1, :]
    b = actual_verts[:, 0, :] - actual_verts[:, 2, :]
    del actual_verts

    # Area of triangle = 1/2 * Euclidean norm of cross product
    return ((np.cross(a, b) ** 2).sum(axis=1) ** 0.5).sum() / 2.
