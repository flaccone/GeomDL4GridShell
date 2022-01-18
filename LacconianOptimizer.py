import torch
import time
from LacconianCalculus import LacconianCalculus
from LaplacianSmoothing import LaplacianSmoothing
from NormalConsistency import NormalConsistency
from models.layers.mesh import Mesh
from options.optimizer_options import OptimizerOptions
from utils import save_mesh


class LacconianOptimizer:

    def __init__(self, file, lr, device, init_mode, beam_have_load, with_laplacian_smooth, with_normal_consistency):
        self.mesh = Mesh(file=file, device=device)
        self.lacconian_calculus = LacconianCalculus(device=device, mesh=self.mesh, beam_have_load=beam_have_load)
        if with_laplacian_smooth:
            self.laplacian_smoothing = LaplacianSmoothing(device=device)
        if with_normal_consistency:
            self.normal_consistency = NormalConsistency(self.mesh, device=device)
        self.device = torch.device(device)

        # Initializing displacements.
        if init_mode == 'stress_aided':
            self.lc = LacconianCalculus(file=file, device=device, beam_have_load=beam_have_load)
            self.displacements = -self.lc.vertex_deformations[self.lc.non_constrained_vertices, :3]
            self.displacements.requires_grad_()
        elif init_mode == 'uniform':
            self.displacements = torch.distributions.Uniform(0,1e-6).sample((len(self.mesh.vertices[self.lacconian_calculus.non_constrained_vertices]), 3))
            self.displacements = self.displacements.to(device)
            self.displacements.requires_grad = True
        elif init_mode == 'normal':
            self.displacements = torch.distributions.Normal(0,1e-6).sample((len(self.mesh.vertices[self.lacconian_calculus.non_constrained_vertices]), 3))
            self.displacements = self.displacements.to(device)
            self.displacements.requires_grad = True
        elif init_mode == 'zeros':
            self.displacements = torch.zeros(len(self.mesh.vertices[self.lacconian_calculus.non_constrained_vertices]), 3, device=self.device, requires_grad=True)

        # Building optimizer.
        self.optimizer = torch.optim.Adam([ self.displacements ], lr=lr)

    def start(self, n_iter, plot, save, plot_save_interval, display_interval, save_label, loss_type):
        for iteration in range(n_iter):
            # self.iter_start = time.time()
            # Putting grads to None.
            self.optimizer.zero_grad(set_to_none=True)

            # Summing displacements to mesh vertices.
            self.mesh.vertices[self.lacconian_calculus.non_constrained_vertices, :] += self.displacements

            # Making on mesh loss-shared computations.
            self.mesh.make_on_mesh_shared_computations()

            # Plotting/saving.
            if iteration % plot_save_interval == 0:
                if plot:
                    colors = torch.norm(self.lacconian_calculus.vertex_deformations[:, :3], p=2, dim=1)
                    self.mesh.plot_mesh(colors=colors)

                if save:
                    filename = save_label + '_' + str(iteration) + '.ply'
                    quality = torch.norm(self.lacconian_calculus.vertex_deformations[:, :3], p=2, dim=1)
                    save_mesh(self.mesh, filename, v_quality=quality.unsqueeze(1))

            loss = self.lacconian_calculus(loss_type)
            if hasattr(self, 'laplacian_smoothing'):
                loss += self.laplacian_smoothing(self.mesh)
            if hasattr(self, 'normal_consistency'):
                loss += self.normal_consistency()

            if iteration % display_interval == 0:
                print('Iteration: ', iteration, ' Loss: ', loss)

            # Computing gradients and updating optimizer
            # self.back_start = time.time()
            loss.backward()
            # self.back_end = time.time()
            self.optimizer.step()

            # Deleting grad history in all re-usable attributes.
            self.lacconian_calculus.clean_attributes()
            # self.iter_end = time.time()
            # print('Iteration time: ' + str(self.iter_end - self.iter_start))
            # print('Backward time: ' + str(self.back_end - self.back_start))

parser = OptimizerOptions()
options = parser.parse()
lo = LacconianOptimizer(options.path, options.lr, options.device, options.init_mode, options.beam_have_load, options.with_laplacian_smooth, options.with_normal_consistency)
lo.start(options.n_iter, options.plot, options.save, options.plot_save_interval, options.display_interval, options.save_label, options.loss_type)
