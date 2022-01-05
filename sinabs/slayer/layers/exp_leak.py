import torch
from sinabs.slayer.leaky import LeakyIntegrator
from sinabs.layers import ExpLeak as ExpLeakSinabs
from sinabs.layers import SqueezeMixin


__all__ = ["ExpLeak", "ExpLeakSqueeze"]


class ExpLeak(ExpLeakSinabs):
    """
    Slayer implementation of an integrator with exponential leak.
    """

    backend = "slayer"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # - Make sure buffers and parameters are on cuda
        self.cuda()

    def forward(self, input_current: "torch.tensor") -> "torch.tensor":
        """
        Forward pass.

        Parameters
        ----------
        input_current : torch.tensor
            Expected shape: (Batch, Time, *...)

        Returns
        -------
        torch.tensor
            ExpLeak layer states. Same shape as `input_current`
        """

        # Ensure the neuron states are initialized
        shape_without_time = (input_current.shape[0], *input_current.shape[2:])
        if self.v_mem.shape != shape_without_time:
            self.reset_states(shape=shape_without_time, randomize=False)

        # Determine no. of time steps from input
        time_steps = input_current.shape[1]

        # Reshape input to 2D -> (N, Time)
        input_2d = input_current.movedim(1, -1).flatten(end_dim=-2).contiguous()

        # Actual evolution of states
        states = LeakyIntegrator.apply(
            input_2d, self.v_mem.flatten().contiguous(), self.alpha
        )

        # Reshape states to original shape -> (Batch, Time, ...)
        states = states.reshape(*shape_without_time, time_steps).movedim(-1, 1)

        # Store current state based on last evolution time step
        self.v_mem = states[:, -1, ...].clone()

        self.tw = time_steps

        return states


class ExpLeakSqueeze(ExpLeak, SqueezeMixin):
    """
    Same as parent class, only takes in squeezed 4D input (Batch*Time, Channel, Height, Width) 
    instead of 5D input (Batch, Time, Channel, Height, Width) in order to be compatible with
    layers that can only take a 4D input, such as convolutional and pooling layers. 
    """
    def __init__(self,
                 batch_size = None,
                 num_timesteps = None,
                 **kwargs,
                ):
        super().__init__(**kwargs)
        self.squeeze_init(batch_size, num_timesteps)
    
    def forward(self, input_data: torch.Tensor) -> torch.Tensor:
        return self.squeeze_forward(input_data, super().forward)

    @property
    def _param_dict(self) -> dict:
        return self.squeeze_param_dict(super()._param_dict)