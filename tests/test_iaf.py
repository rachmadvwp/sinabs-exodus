import pytest
import time
import torch
import torch.nn as nn
import sinabs.slayer.layers as ssl
import sinabs.layers as sl
import sinabs.activation as sa


atol = 1e-5
rtol = 1e-4


def test_lif_basic():
    batch_size, time_steps = 10, 100
    tau_mem = torch.tensor(30.0)
    alpha = torch.exp(-1 / tau_mem)
    input_current = torch.rand(batch_size, time_steps, 2, 7, 7).cuda()
    layer = ssl.IAF().cuda()
    spike_output = layer(input_current)

    assert input_current.shape == spike_output.shape
    assert torch.isnan(spike_output).sum() == 0
    assert spike_output.sum() > 0


def test_lif_squeeze():
    batch_size, time_steps = 10, 100
    input_data = torch.rand(batch_size * time_steps, 2, 7, 7).cuda()
    layer = ssl.IAFSqueeze(batch_size=batch_size).cuda()
    spike_output = layer(input_data)

    assert input_data.shape == spike_output.shape
    assert torch.isnan(spike_output).sum() == 0
    assert spike_output.sum() > 0


def test_threshold_low():
    batch_size, time_steps = 10, 1
    tau_mem = torch.tensor(30.0)
    alpha = torch.exp(-1 / tau_mem)
    input_data = torch.rand(batch_size, time_steps, 2, 7, 7).cuda() / -(1 - alpha)
    layer = ssl.LIF(tau_mem=tau_mem).cuda()
    layer(input_data)
    assert (layer.v_mem < -0.5).any()

    layer = ssl.LIF(tau_mem=tau_mem, threshold_low=-0.5).cuda()
    layer(input_data)
    assert not (layer.v_mem < -0.5).any()


def test_state_reset():
    batch_size, time_steps = 10, 100
    tau_mem = torch.tensor(30.0)
    alpha = torch.exp(-1 / tau_mem)
    input_data = torch.rand(batch_size, time_steps, 2, 7, 7).cuda() / (1 - alpha)
    layer = ssl.LIF(tau_mem=tau_mem).cuda()
    layer.reset_states()
    layer(input_data)
    assert (layer.v_mem != 0).any()

    layer.reset_states()
    assert (layer.v_mem == 0).all()


def test_slayer_sinabs_layer_equal_output():
    batch_size, time_steps = 10, 100
    n_input_channels = 16
    sinabs_model = sl.IAF().cuda()
    slayer_model = ssl.IAF().cuda()
    input_data = torch.zeros((batch_size, time_steps, n_input_channels)).cuda()
    input_data[:, :10] = 1e4
    spike_output_sinabs = sinabs_model(input_data)
    spike_output_slayer = slayer_model(input_data)

    assert spike_output_sinabs.shape == spike_output_slayer.shape
    assert spike_output_sinabs.sum() > 0
    assert spike_output_sinabs.sum() == spike_output_slayer.sum()
    assert (spike_output_sinabs == spike_output_slayer).all()


def test_slayer_sinabs_layer_equal_output_singlespike():
    batch_size, time_steps = 10, 100
    n_input_channels = 16
    activation_fn = sa.ActivationFunction(spike_fn=sa.SingleSpike)
    sinabs_model = sl.IAF(activation_fn=activation_fn).cuda()
    slayer_model = ssl.IAF(activation_fn=activation_fn).cuda()
    input_data = torch.zeros((batch_size, time_steps, n_input_channels)).cuda()
    input_data[:, :10] = 1e4
    spike_output_sinabs = sinabs_model(input_data)
    spike_output_slayer = slayer_model(input_data)

    assert spike_output_sinabs.shape == spike_output_slayer.shape
    assert spike_output_sinabs.sum() > 0
    assert spike_output_sinabs.sum() == spike_output_slayer.sum()
    assert (spike_output_sinabs == spike_output_slayer).all()


def test_sinabs_model():
    batch_size, time_steps = 10, 100
    n_input_channels, n_output_classes = 16, 10
    model = SinabsIAFModel(
        n_input_channels=n_input_channels, n_output_classes=n_output_classes
    ).cuda()
    input_data = torch.rand((batch_size, time_steps, n_input_channels)).cuda() * 1e5
    spike_output = model(input_data)

    assert spike_output.shape == (batch_size, time_steps, n_output_classes)
    assert torch.isnan(spike_output).sum() == 0
    assert spike_output.sum() > 0


def test_slayer_model():
    batch_size, time_steps = 10, 100
    n_input_channels, n_output_classes = 16, 10
    model = SlayerIAFModel(
        n_input_channels=n_input_channels, n_output_classes=n_output_classes
    ).cuda()
    input_data = torch.rand((batch_size, time_steps, n_input_channels)).cuda() * 1e5
    spike_output = model(input_data)

    assert spike_output.shape == (batch_size, time_steps, n_output_classes)
    assert torch.isnan(spike_output).sum() == 0
    assert spike_output.sum() > 0


def test_slayer_sinabs_model_equal_output():
    batch_size, time_steps = 10, 100
    n_input_channels, n_output_classes = 16, 10
    sinabs_model = SinabsIAFModel(
        n_input_channels=n_input_channels, n_output_classes=n_output_classes
    ).cuda()
    slayer_model = SlayerIAFModel(
        n_input_channels=n_input_channels, n_output_classes=n_output_classes
    ).cuda()
    # make sure the weights for linear layers are the same
    for (sinabs_layer, slayer_layer) in zip(
        sinabs_model.linear_layers, slayer_model.linear_layers
    ):
        sinabs_layer.load_state_dict(slayer_layer.state_dict())
    assert (sinabs_model[0].weight == slayer_model[0].weight).all()
    input_data = torch.rand((batch_size, time_steps, n_input_channels)).cuda() * 1e5
    spike_output_sinabs = sinabs_model(input_data)
    spike_output_slayer = slayer_model(input_data)

    assert spike_output_sinabs.shape == spike_output_slayer.shape
    assert spike_output_sinabs.sum() == spike_output_slayer.sum()
    assert (spike_output_sinabs == spike_output_slayer).all()


def test_slayer_vs_sinabs_compare_grads():
    batch_size, time_steps = 10, 100
    n_input_channels, n_output_classes = 16, 10
    sinabs_model = SinabsIAFModel(
        n_input_channels=n_input_channels, n_output_classes=n_output_classes
    ).cuda()
    slayer_model = SlayerIAFModel(
        n_input_channels=n_input_channels, n_output_classes=n_output_classes
    ).cuda()

    # make sure the weights for linear layers are the same
    for (sinabs_layer, slayer_layer) in zip(
        sinabs_model.linear_layers, slayer_model.linear_layers
    ):
        sinabs_layer.load_state_dict(slayer_layer.state_dict())
    assert (sinabs_model[0].weight == slayer_model[0].weight).all()

    input_data = torch.rand((batch_size, time_steps, n_input_channels)).cuda() * 1e5

    t_start = time.time()
    sinabs_out = sinabs_model(input_data)
    loss_sinabs = torch.nn.functional.mse_loss(sinabs_out, torch.ones_like(sinabs_out))
    loss_sinabs.backward()
    grads_sinabs = [
        p.grad.data.clone() for p in sinabs_model.parameters() if p.grad is not None
    ]
    print(f"Runtime sinabs: {time.time() - t_start}")

    slayer_model.zero_grad()
    t_start = time.time()
    slayer_out = slayer_model(input_data)
    loss_slayer = torch.nn.functional.mse_loss(slayer_out, torch.ones_like(slayer_out))
    loss_slayer.backward()
    grads_slayer = [p.grad.data.clone() for p in slayer_model.parameters()]
    print(f"Runtime slayer: {time.time() - t_start}")

    for (l_sin, l_slyr) in zip(
        slayer_model.spiking_layers, sinabs_model.spiking_layers
    ):
        assert torch.allclose(l_sin.v_mem, l_slyr.v_mem, atol=atol, rtol=rtol)

    assert (sinabs_out == slayer_out).all()

    for g0, g1 in zip(grads_sinabs, grads_slayer):
        assert torch.allclose(g0, g1, atol=atol, rtol=rtol)


class SinabsIAFModel(nn.Sequential):
    def __init__(
        self,
        n_input_channels=16,
        n_output_classes=10,
        threshold=1.0,
        threshold_low=None,
    ):
        act_fn = sa.ActivationFunction(spike_threshold=threshold)
        super().__init__(
            nn.Linear(n_input_channels, 16, bias=False),
            sl.IAF(activation_fn=act_fn, threshold_low=threshold_low),
            nn.Linear(16, 32, bias=False),
            sl.IAF(activation_fn=act_fn, threshold_low=threshold_low),
            nn.Linear(32, n_output_classes, bias=False),
            sl.IAF(activation_fn=act_fn, threshold_low=threshold_low),
        )

    def reset_states(self):
        for lyr in self.spiking_layers:
            lyr.reset_states()

    def zero_grad(self):
        for lyr in self.spiking_layers:
            lyr.zero_grad()

    @property
    def spiking_layers(self):
        return [self[1], self[3], self[5]]

    @property
    def linear_layers(self):
        return [self[0], self[2], self[4]]


class SlayerIAFModel(nn.Sequential):
    def __init__(
        self,
        n_input_channels=16,
        n_output_classes=10,
        threshold=1.0,
        threshold_low=None,
    ):
        act_fn = sa.ActivationFunction(spike_threshold=threshold)
        super().__init__(
            nn.Linear(n_input_channels, 16, bias=False),
            ssl.IAF(activation_fn=act_fn, threshold_low=threshold_low),
            nn.Linear(16, 32, bias=False),
            ssl.IAF(activation_fn=act_fn, threshold_low=threshold_low),
            nn.Linear(32, n_output_classes, bias=False),
            ssl.IAF(activation_fn=act_fn, threshold_low=threshold_low),
        )

    def reset_states(self):
        for lyr in self.spiking_layers:
            lyr.reset_states()

    def zero_grad(self):
        for lyr in self.spiking_layers:
            lyr.zero_grad()

    @property
    def spiking_layers(self):
        return [self[1], self[3], self[5]]

    @property
    def linear_layers(self):
        return [self[0], self[2], self[4]]
