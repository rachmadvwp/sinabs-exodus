def test_iaf_inference():
    import torch
    import pytest
    from sinabs.slayer.layers import IAFSqueeze, IAF

    num_timesteps = 100
    threshold = 0.2
    threshold_low = -0.2
    batch_size = 32
    n_neurons = (3, 3, 5)

    device = "cuda:0"

    spikes_pos = torch.rand((batch_size, num_timesteps, *n_neurons)) > 0.95
    spikes_neg = torch.rand((batch_size, num_timesteps, *n_neurons)) > 0.9
    input_data = (spikes_pos.float() - spikes_neg.float()).to(device)
    input_data_squeeze = input_data.reshape(-1, *n_neurons)

    layer_squeeze = IAFSqueeze(num_timesteps=num_timesteps, threshold=threshold).to(
        device
    )
    layer_squeeze_thr_low = IAFSqueeze(
        num_timesteps=num_timesteps, threshold=threshold, threshold_low=threshold_low
    ).to(device)
    layer = IAF(num_timesteps=num_timesteps, threshold=threshold).to(device)

    # Make sure wrong input dimensions are detected
    with pytest.raises(ValueError):
        output = layer(torch.rand((batch_size, num_timesteps + 1, *n_neurons)))

    output = layer(input_data)
    assert output.shape == input_data.shape

    output_squeeze = layer_squeeze(input_data_squeeze)
    assert output_squeeze.shape == input_data_squeeze.shape
    assert (output_squeeze == output.reshape(-1, *n_neurons)).all()

    output_thrlow = layer_squeeze_thr_low(input_data_squeeze)
    assert (output_thrlow != output_squeeze).any()

    # # Make sure vmem is not below threshold_low for two consecutive timesteps
    # # This test might fail even if the layer works correctly
    # vmem = layer_squeeze_thr_low.vmem
    # assert not (
    #     torch.logical_and(vmem[:, 1:] < threshold_low, vmem[:, :-1] < threshold_low)
    # ).any()


def build_sinabs_model(
    n_channels=16, n_classes=10, batch_size=1, threshold=1.0, threshold_low=None
):
    import torch.nn as nn
    from sinabs.layers import IAFSqueeze

    class TestModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.lin1 = nn.Linear(n_channels, 16, bias=False)
            self.spk1 = IAFSqueeze(
                threshold=threshold, threshold_low=threshold_low, batch_size=batch_size
            )
            self.lin2 = nn.Linear(16, 32, bias=False)
            self.spk2 = IAFSqueeze(
                threshold=threshold, threshold_low=threshold_low, batch_size=batch_size
            )
            self.lin3 = nn.Linear(32, n_classes, bias=False)
            self.spk3 = IAFSqueeze(
                threshold=threshold, threshold_low=threshold_low, batch_size=batch_size
            )

        def forward(self, data):
            out = self.lin1(data)
            out = self.spk1(out)
            out = self.lin2(out)
            out = self.spk2(out)
            out = self.lin3(out)
            out = self.spk3(out)
            return out

        def reset_states(self):
            for lyr in self.spiking_layers:
                lyr.reset_states()

        def zero_grad(self):
            for lyr in self.spiking_layers:
                lyr.zero_grad()

        @property
        def spiking_layers(self):
            return [self.spk1, self.spk2, self.spk3]

    return TestModel()


def test_sinabs_model():
    import torch

    num_timesteps = 100
    n_channels = 16
    batch_size = 2
    n_classes = 10
    device = "cuda:0"
    model = build_sinabs_model(
        n_channels=n_channels, n_classes=n_classes, batch_size=1
    ).to(device)
    input_data = torch.rand((batch_size * num_timesteps, n_channels)).to(device)
    out = model(input_data)
    assert out.shape == (batch_size * num_timesteps, n_classes)


def build_slayer_model(
    n_channels=16,
    n_classes=10,
    num_timesteps=100,
    scale_grads=1.0,
    threshold=1.0,
    threshold_low=None,
):
    import torch.nn as nn
    from sinabs.slayer.layers import IAFSqueeze

    class TestModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.lin1 = nn.Linear(n_channels, 16, bias=False)
            self.spk1 = IAFSqueeze(
                num_timesteps=num_timesteps,
                threshold=threshold,
                threshold_low=threshold_low,
                scale_grads=scale_grads,
            )
            self.lin2 = nn.Linear(16, 32, bias=False)
            self.spk2 = IAFSqueeze(
                num_timesteps=num_timesteps,
                threshold=threshold,
                threshold_low=threshold_low,
                scale_grads=scale_grads,
            )
            self.lin3 = nn.Linear(32, n_classes, bias=False)
            self.spk3 = IAFSqueeze(
                num_timesteps=num_timesteps,
                threshold=threshold,
                threshold_low=threshold_low,
                scale_grads=scale_grads,
            )

        def forward(self, data):
            out = self.lin1(data)
            out = self.spk1(out)
            out = self.lin2(out)
            out = self.spk2(out)
            out = self.lin3(out)
            out = self.spk3(out)
            return out

        def reset_states(self):
            for lyr in self.spiking_layers:
                lyr.reset_states()

        def zero_grad(self):
            for lyr in self.spiking_layers:
                lyr.zero_grad()

        @property
        def spiking_layers(self):
            return [self.spk1, self.spk2, self.spk3]

    return TestModel()


def test_slayer_model():
    import torch

    num_timesteps = 100
    n_channels = 16
    batch_size = 2
    n_classes = 10
    device = "cuda:0"
    model = build_slayer_model(
        n_channels=n_channels, n_classes=n_classes, num_timesteps=num_timesteps
    ).to(device)

    input_data = torch.rand((num_timesteps * batch_size, n_channels)).to(device)

    out = model(input_data)
    assert out.shape == (num_timesteps * batch_size, n_classes)


def test_gradient_scaling():
    import torch

    torch.manual_seed(0)
    num_timesteps = 100
    n_channels = 16
    batch_size = 1
    n_classes = 2
    device = "cuda:0"
    model = build_slayer_model(
        n_channels=n_channels,
        n_classes=n_classes,
        num_timesteps=num_timesteps,
        threshold=0.1,
        threshold_low=-0.1,
    ).to(device)
    initial_weights = [p.data.clone() for p in model.parameters()]
    input_data = torch.rand((num_timesteps * batch_size, n_channels)).to(device)

    out = model(input_data).cpu()
    loss = torch.nn.functional.mse_loss(out, torch.ones_like(out))
    loss.backward()
    grads = [p.grad for p in model.parameters()]
    # Calculate ratio of std of first and last layer gradients
    grad_ratio = torch.std(grads[0]) / torch.std(grads[-1])

    # Generate identical model, except for gradient scaling
    model_new = build_slayer_model(
        n_channels=n_channels,
        n_classes=n_classes,
        num_timesteps=num_timesteps,
        scale_grads=0.1,
        threshold=0.1,
        threshold_low=-0.1,
    ).to(device)
    for p_new, p_old in zip(model_new.parameters(), initial_weights):
        p_new.data = p_old.clone()

    out_new = model_new(input_data).cpu()
    # Make sure output is the same as for original model
    assert (out_new == out).all()

    # Compare gradient ratios
    loss_new = torch.nn.functional.mse_loss(out_new, torch.ones_like(out))

    # Make sure loss is the same as for original model
    assert (loss_new == loss).all()

    loss_new.backward()
    grads_new = [p.grad for p in model_new.parameters()]
    grad_ratio_new = torch.std(grads_new[0]) / torch.std(grads_new[-1])

    # Deepest layer gradient should be much smaller than before
    assert grad_ratio_new < 0.5 * grad_ratio


def test_slayer_vs_sinabs_compare():
    import torch
    import time

    num_timesteps = 500
    n_channels = 16
    batch_size = 100
    n_classes = 10
    device = "cuda:0"

    # Define inputs
    input_data = (
        (torch.rand((num_timesteps * batch_size, n_channels)) > 0.95).float().to(device)
    )

    # Define models
    slayer_model = build_slayer_model(
        n_channels=n_channels, n_classes=n_classes, num_timesteps=num_timesteps
    ).to(device)
    sinabs_model = build_sinabs_model(
        n_channels=n_channels, n_classes=n_classes, batch_size=batch_size
    ).to(device)

    def scale_all_weights_by_x(model, x):
        for param in model.parameters():
            param.data = param.data * x

    scale_all_weights_by_x(sinabs_model, 1.0)

    # Copy parameters
    slayer_model.lin1.weight.data = sinabs_model.lin1.weight.data.clone()
    slayer_model.lin2.weight.data = sinabs_model.lin2.weight.data.clone()
    slayer_model.lin3.weight.data = sinabs_model.lin3.weight.data.clone()

    # Optimizers for comparing gradients
    optim_slayer = torch.optim.SGD(slayer_model.parameters(), lr=1e-3)
    optim_sinabs = torch.optim.SGD(sinabs_model.parameters(), lr=1e-3)

    for i in range(3):
        # Sinabs
        sinabs_model.zero_grad()
        optim_sinabs.zero_grad()
        t_start = time.time()
        sinabs_out = sinabs_model(input_data.view((-1, n_channels)))
        loss_sinabs = torch.nn.functional.mse_loss(
            sinabs_out, torch.ones_like(sinabs_out)
        )
        loss_sinabs.backward()
        grads_sinabs = [p.grad.data.clone() for p in sinabs_model.parameters()]
        optim_sinabs.step()

        t_stop = time.time()
        print(f"Runtime sinabs: {t_stop - t_start}")
        print("Sinabs model: ", sinabs_out.sum())

        # Slayer
        slayer_model.zero_grad()
        optim_slayer.zero_grad()
        t_start = time.time()
        slayer_out = slayer_model(input_data)
        loss_slayer = torch.nn.functional.mse_loss(
            slayer_out, torch.ones_like(slayer_out)
        )
        loss_slayer.backward()
        grads_slayer = [p.grad.data.clone() for p in slayer_model.parameters()]
        optim_slayer.step()
        t_stop = time.time()
        print(f"Runtime slayer: {t_stop - t_start}")
        print("Slayer model: ", slayer_out.sum())
        # print(slayer_out)

        ## Plot data
        # import matplotlib.pyplot as plt
        # plt.plot(sinabs_model.spk1.record[:, 0, 0].detach().cpu(), label="sinabs")
        # plt.plot(slayer_model.spk1.vmem[0, 0, 0, 0].detach().cpu(), label="Slayer")
        # plt.legend()
        # plt.show()
        # plt.figure()
        # plt.scatter(*np.where(sinabs_out.cpu().detach().numpy()), marker=".")
        # plt.scatter(*np.where(slayer_out.cpu().detach().numpy()), marker="x")
        # plt.show()

        assert all(
            torch.allclose(l_sin.state, l_slyr.state)
            for (l_sin, l_slyr) in zip(
                slayer_model.spiking_layers, sinabs_model.spiking_layers
            )
        )
        assert (sinabs_out == slayer_out).all()

        # Compare gradients
        assert all(torch.allclose(g0, g1) for g0, g1 in zip(grads_sinabs, grads_slayer))


def test_slayer_vs_sinabs_compare_thr_low():
    import torch
    import time

    num_timesteps = 500
    n_channels = 16
    batch_size = 100
    n_classes = 10
    device = "cuda:0"

    # Define inputs
    input_data = (
        (torch.rand((num_timesteps * batch_size, n_channels)) > 0.95).float().to(device)
    )

    # Define models
    slayer_model = build_slayer_model(
        n_channels=n_channels,
        n_classes=n_classes,
        num_timesteps=num_timesteps,
        threshold_low=-1,
    ).to(device)
    sinabs_model = build_sinabs_model(
        n_channels=n_channels,
        n_classes=n_classes,
        batch_size=batch_size,
        threshold_low=-1,
    ).to(device)

    # Copy parameters
    slayer_model.lin1.weight.data = sinabs_model.lin1.weight.data.clone()
    slayer_model.lin2.weight.data = sinabs_model.lin2.weight.data.clone()
    slayer_model.lin3.weight.data = sinabs_model.lin3.weight.data.clone()

    # Optimizers for comparing gradients
    optim_slayer = torch.optim.SGD(slayer_model.parameters(), lr=1e-3)
    optim_sinabs = torch.optim.SGD(sinabs_model.parameters(), lr=1e-3)

    for i in range(3):
        # Sinabs
        sinabs_model.zero_grad()
        optim_sinabs.zero_grad()
        t_start = time.time()
        sinabs_out = sinabs_model(input_data.view((-1, n_channels)))
        loss_sinabs = torch.nn.functional.mse_loss(
            sinabs_out, torch.ones_like(sinabs_out)
        )
        loss_sinabs.backward()
        grads_sinabs = [p.grad.data.clone() for p in sinabs_model.parameters()]
        optim_sinabs.step()

        t_stop = time.time()
        print(f"Runtime sinabs: {t_stop - t_start}")
        print("Sinabs model: ", sinabs_out.sum())

        # Slayer
        slayer_model.zero_grad()
        optim_slayer.zero_grad()
        t_start = time.time()
        slayer_out = slayer_model(input_data)
        loss_slayer = torch.nn.functional.mse_loss(
            slayer_out, torch.ones_like(slayer_out)
        )
        loss_slayer.backward()
        grads_slayer = [p.grad.data.clone() for p in slayer_model.parameters()]
        optim_slayer.step()
        t_stop = time.time()
        print(f"Runtime slayer: {t_stop - t_start}")

        print("Slayer model: ", slayer_out.sum())
        # print(slayer_out)

        ## Plot data
        # import matplotlib.pyplot as plt
        # plt.plot(sinabs_model.spk1.record[:, 0, 0].detach().cpu(), label="sinabs")
        # plt.plot(slayer_model.spk1.vmem[0, 0, 0, 0].detach().cpu(), label="Slayer")
        # plt.legend()
        # plt.show()
        # plt.figure()
        # plt.scatter(*np.where(sinabs_out.cpu().detach().numpy()), marker=".")
        # plt.scatter(*np.where(slayer_out.cpu().detach().numpy()), marker="x")
        # plt.show()

        assert all(
            torch.allclose(l_sin.state, l_slyr.state)
            for (l_sin, l_slyr) in zip(
                slayer_model.spiking_layers, sinabs_model.spiking_layers
            )
        )
        assert (sinabs_out == slayer_out).all()

        # Compare gradients
        assert all(torch.allclose(g0, g1) for g0, g1 in zip(grads_sinabs, grads_slayer))


def test_slayer_vs_sinabs_compare_thr_low_reset():
    import torch
    import time

    num_timesteps = 500
    n_channels = 16
    batch_size = 100
    n_classes = 10
    device = "cuda:0"

    # Define inputs
    input_data = (
        (torch.rand((num_timesteps * batch_size, n_channels)) > 0.95).float().to(device)
    )

    # Define models
    slayer_model = build_slayer_model(
        n_channels=n_channels,
        n_classes=n_classes,
        num_timesteps=num_timesteps,
        threshold_low=-1,
    ).to(device)
    sinabs_model = build_sinabs_model(
        n_channels=n_channels,
        n_classes=n_classes,
        batch_size=batch_size,
        threshold_low=-1,
    ).to(device)

    # Copy parameters
    slayer_model.lin1.weight.data = sinabs_model.lin1.weight.data.clone()
    slayer_model.lin2.weight.data = sinabs_model.lin2.weight.data.clone()
    slayer_model.lin3.weight.data = sinabs_model.lin3.weight.data.clone()

    # Optimizers for comparing gradients
    optim_slayer = torch.optim.SGD(slayer_model.parameters(), lr=1e-3)
    optim_sinabs = torch.optim.SGD(sinabs_model.parameters(), lr=1e-3)

    for i in range(3):
        # Sinabs
        sinabs_model.reset_states()
        optim_sinabs.zero_grad()
        t_start = time.time()
        sinabs_out = sinabs_model(input_data.view((-1, n_channels)))
        loss_sinabs = torch.nn.functional.mse_loss(
            sinabs_out, torch.ones_like(sinabs_out)
        )
        loss_sinabs.backward()
        grads_sinabs = [p.grad.data.clone() for p in sinabs_model.parameters()]
        optim_sinabs.step()

        t_stop = time.time()
        print(f"Runtime sinabs: {t_stop - t_start}")
        print("Sinabs model: ", sinabs_out.sum())

        # Slayer
        slayer_model.reset_states()
        optim_slayer.zero_grad()
        t_start = time.time()
        slayer_out = slayer_model(input_data)
        loss_slayer = torch.nn.functional.mse_loss(
            slayer_out, torch.ones_like(slayer_out)
        )
        loss_slayer.backward()
        grads_slayer = [p.grad.data.clone() for p in slayer_model.parameters()]
        optim_slayer.step()
        t_stop = time.time()
        print(f"Runtime slayer: {t_stop - t_start}")

        print("Slayer model: ", slayer_out.sum())
        # print(slayer_out)

        ## Plot data
        # import matplotlib.pyplot as plt
        # plt.plot(sinabs_model.spk1.record[:, 0, 0].detach().cpu(), label="sinabs")
        # plt.plot(slayer_model.spk1.vmem[0, 0, 0, 0].detach().cpu(), label="Slayer")
        # plt.legend()
        # plt.show()
        # plt.figure()
        # plt.scatter(*np.where(sinabs_out.cpu().detach().numpy()), marker=".")
        # plt.scatter(*np.where(slayer_out.cpu().detach().numpy()), marker="x")
        # plt.show()

        assert all(
            torch.allclose(l_sin.state, l_slyr.state)
            for (l_sin, l_slyr) in zip(
                slayer_model.spiking_layers, sinabs_model.spiking_layers
            )
        )
        assert (sinabs_out == slayer_out).all()

        # Compare gradients
        assert all(torch.allclose(g0, g1) for g0, g1 in zip(grads_sinabs, grads_slayer))