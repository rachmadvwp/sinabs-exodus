def test_generateEpsp():
    import torch
    from sinabs.slayer.psp import generateEpsp
    from sinabs.slayer.kernels import psp_kernels

    device = "cuda:0"

    kernels = psp_kernels([10, 15], 10.0, 1).to(device)

    # n_syn, n_neurons, t_sim
    input_spikes = torch.rand(2, 7, 100).to(device)
    t_sim = input_spikes.shape[-1]

    vsyn = generateEpsp(input_spikes, kernels)
    assert vsyn.shape == (2, 7, 100)
